#!/usr/bin/env python3
"""
Prompt Evolution Experiment

Runs genetic algorithm optimization on prompt compositions using real
conversation performance as fitness, similar to DSPy's approach.
"""

import os
import sys
import json
import asyncio
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import argparse

# Add project paths
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from prompts.composition_evolution import CompositionEvolver, CompositionGenome
from prompts.fitness_evaluator import FitnessEvaluator

logger = logging.getLogger('prompt_evolution')


class EvolutionExperiment:
    """Manages a complete prompt evolution experiment"""
    
    def __init__(self, 
                 experiment_name: str,
                 population_size: int = 12,
                 generations: int = 5,
                 mutation_rate: float = 0.2,
                 crossover_rate: float = 0.8):
        
        self.experiment_name = experiment_name
        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        
        # Create results directory
        self.results_dir = f"experiments/results/{experiment_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.makedirs(self.results_dir, exist_ok=True)
        
        # Initialize components
        self.evolver = CompositionEvolver(
            population_size=population_size,
            mutation_rate=mutation_rate,
            crossover_rate=crossover_rate
        )
        self.evaluator = FitnessEvaluator()
        
        # Experiment tracking
        self.generation_results = []
        self.best_genome_history = []
    
    async def run_experiment(self, base_compositions: List[str] = None):
        """Run the complete evolution experiment"""
        logger.info(f"Starting experiment: {self.experiment_name}")
        logger.info(f"Parameters: pop={self.population_size}, gen={self.generations}, mut={self.mutation_rate}, cross={self.crossover_rate}")
        
        # Initialize population
        await self.evolver.initialize_population(base_compositions)
        
        # Run evolution for specified generations
        for generation in range(self.generations):
            logger.info(f"\n{'='*50}")
            logger.info(f"GENERATION {generation + 1}/{self.generations}")
            logger.info(f"{'='*50}")
            
            # Evaluate all genomes in current population
            generation_data = await self._evaluate_generation(generation)
            
            # Track results
            self.generation_results.append(generation_data)
            self.best_genome_history.append(generation_data['best_genome'])
            
            # Save intermediate results
            await self._save_generation_results(generation, generation_data)
            
            # Evolve to next generation (unless this is the last one)
            if generation < self.generations - 1:
                await self.evolver.evolve_generation()
        
        # Save final results
        await self._save_final_results()
        
        logger.info(f"\nExperiment complete! Results saved to: {self.results_dir}")
        return self._generate_summary()
    
    async def _evaluate_generation(self, generation: int) -> Dict[str, Any]:
        """Evaluate all genomes in the current generation"""
        logger.info(f"Evaluating {len(self.evolver.population)} genomes...")
        
        generation_data = {
            'generation': generation,
            'timestamp': datetime.now().isoformat(),
            'genomes': [],
            'best_genome': None,
            'avg_fitness': 0.0,
            'fitness_std': 0.0
        }
        
        fitness_scores = []
        
        for i, genome in enumerate(self.evolver.population):
            logger.info(f"  Evaluating genome {i+1}/{len(self.evolver.population)}: {genome.name}")
            
            try:
                # Create temporary composition file for this genome
                temp_composition = await self._genome_to_composition(genome)
                
                # Evaluate the composition
                scenario_results = await self.evaluator.run_full_evaluation(temp_composition)
                fitness = self.evaluator.calculate_overall_fitness(scenario_results)
                
                # Update genome fitness
                genome.fitness_score = fitness
                fitness_scores.append(fitness)
                
                # Store detailed results
                genome_data = {
                    'name': genome.name,
                    'hash': genome.get_hash(),
                    'fitness': fitness,
                    'generation': genome.generation,
                    'parent_genomes': genome.parent_genomes,
                    'scenario_results': scenario_results,
                    'components': genome.components,
                    'weights': genome.weights
                }
                
                generation_data['genomes'].append(genome_data)
                logger.info(f"    Fitness: {fitness:.3f}")
                
            except Exception as e:
                logger.error(f"    Failed to evaluate genome {genome.name}: {e}")
                genome.fitness_score = 0.0
                fitness_scores.append(0.0)
        
        # Calculate generation statistics
        if fitness_scores:
            generation_data['avg_fitness'] = sum(fitness_scores) / len(fitness_scores)
            generation_data['fitness_std'] = (sum((f - generation_data['avg_fitness'])**2 for f in fitness_scores) / len(fitness_scores))**0.5
            
            # Find best genome
            best_genome = max(self.evolver.population, key=lambda x: x.fitness_score)
            generation_data['best_genome'] = {
                'name': best_genome.name,
                'fitness': best_genome.fitness_score,
                'hash': best_genome.get_hash()
            }
        
        logger.info(f"Generation {generation + 1} summary:")
        logger.info(f"  Best fitness: {generation_data['best_genome']['fitness']:.3f}")
        logger.info(f"  Average fitness: {generation_data['avg_fitness']:.3f}")
        logger.info(f"  Fitness std: {generation_data['fitness_std']:.3f}")
        
        return generation_data
    
    async def _genome_to_composition(self, genome: CompositionGenome) -> str:
        """Convert a genome to a temporary composition file"""
        # Create composition YAML from genome
        composition_data = {
            'name': genome.name,
            'version': '1.0',
            'description': f'Evolved composition (generation {genome.generation})',
            'author': 'evolution_experiment',
            'components': []
        }
        
        # Add components
        for component in genome.components:
            comp_entry = {'name': component.split('/')[-1].replace('.md', ''), 'source': component}
            
            # Add variables if available
            if component in genome.parameters:
                comp_entry.update(genome.parameters[component])
            
            composition_data['components'].append(comp_entry)
        
        # Add metadata
        composition_data['metadata'] = {
            'tags': ['evolved', 'experimental'],
            'evolution_info': {
                'generation': genome.generation,
                'parent_genomes': genome.parent_genomes,
                'weights': genome.weights
            }
        }
        
        # Save to temporary file
        temp_file = f"{self.results_dir}/temp_{genome.name}.yaml"
        with open(temp_file, 'w') as f:
            import yaml
            yaml.dump(composition_data, f, default_flow_style=False)
        
        return genome.name  # Return name for evaluation
    
    async def _save_generation_results(self, generation: int, data: Dict[str, Any]):
        """Save results for a specific generation"""
        filename = f"{self.results_dir}/generation_{generation:02d}.json"
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
    
    async def _save_final_results(self):
        """Save complete experiment results"""
        # Experiment summary
        summary = {
            'experiment_name': self.experiment_name,
            'parameters': {
                'population_size': self.population_size,
                'generations': self.generations,
                'mutation_rate': self.mutation_rate,
                'crossover_rate': self.crossover_rate
            },
            'results': {
                'total_generations': len(self.generation_results),
                'best_final_fitness': max(g['best_genome']['fitness'] for g in self.generation_results),
                'fitness_improvement': (
                    self.generation_results[-1]['best_genome']['fitness'] - 
                    self.generation_results[0]['best_genome']['fitness']
                ) if len(self.generation_results) > 1 else 0.0,
                'generation_results': self.generation_results,
                'best_genome_history': self.best_genome_history
            },
            'timestamp': datetime.now().isoformat()
        }
        
        # Save summary
        with open(f"{self.results_dir}/experiment_summary.json", 'w') as f:
            json.dump(summary, f, indent=2)
        
        # Save best compositions
        best_genomes = [g['best_genome'] for g in self.generation_results]
        with open(f"{self.results_dir}/best_genomes.json", 'w') as f:
            json.dump(best_genomes, f, indent=2)
        
        # Create analysis plots (if matplotlib available)
        try:
            await self._create_analysis_plots()
        except ImportError:
            logger.warning("matplotlib not available, skipping plot generation")
    
    async def _create_analysis_plots(self):
        """Create analysis plots for the experiment"""
        import matplotlib.pyplot as plt
        
        generations = list(range(1, len(self.generation_results) + 1))
        best_fitness = [g['best_genome']['fitness'] for g in self.generation_results]
        avg_fitness = [g['avg_fitness'] for g in self.generation_results]
        
        plt.figure(figsize=(12, 4))
        
        # Fitness over time
        plt.subplot(1, 2, 1)
        plt.plot(generations, best_fitness, 'b-o', label='Best Fitness')
        plt.plot(generations, avg_fitness, 'r-s', label='Average Fitness')
        plt.xlabel('Generation')
        plt.ylabel('Fitness Score')
        plt.title('Fitness Evolution')
        plt.legend()
        plt.grid(True)
        
        # Fitness distribution in final generation
        plt.subplot(1, 2, 2)
        final_fitnesses = [g['fitness'] for g in self.generation_results[-1]['genomes']]
        plt.hist(final_fitnesses, bins=10, alpha=0.7, edgecolor='black')
        plt.xlabel('Fitness Score')
        plt.ylabel('Count')
        plt.title('Final Generation Fitness Distribution')
        plt.grid(True)
        
        plt.tight_layout()
        plt.savefig(f"{self.results_dir}/evolution_analysis.png", dpi=150, bbox_inches='tight')
        plt.close()
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Generate experiment summary"""
        if not self.generation_results:
            return {'status': 'failed', 'message': 'No generations completed'}
        
        initial_fitness = self.generation_results[0]['best_genome']['fitness']
        final_fitness = self.generation_results[-1]['best_genome']['fitness']
        improvement = final_fitness - initial_fitness
        
        return {
            'status': 'completed',
            'experiment_name': self.experiment_name,
            'generations_completed': len(self.generation_results),
            'initial_best_fitness': initial_fitness,
            'final_best_fitness': final_fitness,
            'improvement': improvement,
            'improvement_percent': (improvement / max(initial_fitness, 0.001)) * 100,
            'results_directory': self.results_dir
        }


async def main():
    """Command-line interface for running evolution experiments"""
    parser = argparse.ArgumentParser(description='Run prompt composition evolution experiment')
    parser.add_argument('--name', default='prompt_evolution', help='Experiment name')
    parser.add_argument('--population', type=int, default=8, help='Population size')
    parser.add_argument('--generations', type=int, default=3, help='Number of generations')
    parser.add_argument('--mutation', type=float, default=0.2, help='Mutation rate')
    parser.add_argument('--crossover', type=float, default=0.8, help='Crossover rate')
    parser.add_argument('--compositions', nargs='+', help='Base compositions to start with')
    
    args = parser.parse_args()
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create and run experiment
    experiment = EvolutionExperiment(
        experiment_name=args.name,
        population_size=args.population,
        generations=args.generations,
        mutation_rate=args.mutation,
        crossover_rate=args.crossover
    )
    
    # Use default compositions if none specified
    base_compositions = args.compositions or ['ksi_project_developer', 'conversation_debate']
    
    try:
        summary = await experiment.run_experiment(base_compositions)
        
        print("\n" + "="*60)
        print("EXPERIMENT SUMMARY")
        print("="*60)
        print(f"Experiment: {summary['experiment_name']}")
        print(f"Status: {summary['status']}")
        print(f"Generations: {summary['generations_completed']}")
        print(f"Initial best fitness: {summary['initial_best_fitness']:.3f}")
        print(f"Final best fitness: {summary['final_best_fitness']:.3f}")
        print(f"Improvement: {summary['improvement']:+.3f} ({summary['improvement_percent']:+.1f}%)")
        print(f"Results: {summary['results_directory']}")
        
    except Exception as e:
        logger.error(f"Experiment failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))