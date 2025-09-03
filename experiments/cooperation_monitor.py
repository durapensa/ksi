#!/usr/bin/env python3
"""
Real-time Cooperation Dynamics Monitor
Captures, analyzes, and visualizes cooperation emergence in KSI experiments
"""

import json
import time
import asyncio
import numpy as np
from datetime import datetime
from collections import defaultdict, deque
from typing import Dict, List, Tuple, Any
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.patches import Circle
import networkx as nx

class CooperationMonitor:
    """Real-time monitoring system for cooperation experiments"""
    
    def __init__(self, experiment_id: str):
        self.experiment_id = experiment_id
        self.start_time = time.time()
        
        # Metrics tracking
        self.cooperation_history = deque(maxlen=1000)
        self.trust_network = nx.Graph()
        self.active_norms = []
        self.communication_log = deque(maxlen=500)
        
        # Real-time metrics
        self.metrics = {
            'current_cooperation_rate': 0.0,
            'trust_pairs': [],
            'norm_count': 0,
            'communication_volume': 0,
            'population_composition': {},
            'emergence_indicators': {}
        }
        
        # Time series data
        self.time_series = {
            'timestamps': [],
            'cooperation_rates': [],
            'trust_density': [],
            'norm_adoption': [],
            'communication_impact': []
        }
        
        # Pattern detection
        self.patterns = {
            'tit_for_tat': 0,
            'always_cooperate': 0,
            'always_defect': 0,
            'complex_strategies': 0
        }
        
    def process_event(self, event: Dict[str, Any]):
        """Process incoming KSI events"""
        event_type = event.get('event', '')
        
        if event_type == 'game:move':
            self._process_game_move(event)
        elif event_type == 'message:send':
            self._process_communication(event)
        elif event_type == 'norm:emerged':
            self._process_norm_emergence(event)
        elif event_type == 'trust:formed':
            self._process_trust_formation(event)
        elif event_type == 'state:entity:update':
            self._process_state_update(event)
            
    def _process_game_move(self, event: Dict):
        """Track game moves and cooperation rates"""
        data = event.get('data', {})
        move = data.get('move')
        agent_id = data.get('agent_id')
        opponent_id = data.get('opponent_id')
        round_num = data.get('round', 0)
        
        # Track cooperation
        is_cooperative = move in ['C', 'cooperate', 'COOPERATE']
        self.cooperation_history.append({
            'agent': agent_id,
            'opponent': opponent_id,
            'cooperative': is_cooperative,
            'round': round_num,
            'timestamp': time.time()
        })
        
        # Update cooperation rate
        recent_moves = list(self.cooperation_history)[-100:]
        if recent_moves:
            coop_count = sum(1 for m in recent_moves if m['cooperative'])
            self.metrics['current_cooperation_rate'] = coop_count / len(recent_moves)
            
    def _process_communication(self, event: Dict):
        """Track communication patterns and impact"""
        data = event.get('data', {})
        sender = data.get('sender')
        receiver = data.get('receiver')
        message = data.get('message', '')
        
        self.communication_log.append({
            'sender': sender,
            'receiver': receiver,
            'message': message,
            'timestamp': time.time()
        })
        
        self.metrics['communication_volume'] += 1
        
        # Analyze message sentiment/intent
        if any(word in message.lower() for word in ['cooperate', 'together', 'mutual']):
            self._update_trust_edge(sender, receiver, 0.1)
        elif any(word in message.lower() for word in ['defect', 'punish', 'retaliate']):
            self._update_trust_edge(sender, receiver, -0.1)
            
    def _process_norm_emergence(self, event: Dict):
        """Track emergent norms and behavioral rules"""
        data = event.get('data', {})
        norm = {
            'id': data.get('norm_id'),
            'description': data.get('description'),
            'adopters': data.get('adopters', []),
            'compliance_rate': data.get('compliance_rate', 0),
            'emerged_at': time.time()
        }
        
        self.active_norms.append(norm)
        self.metrics['norm_count'] = len(self.active_norms)
        
    def _process_trust_formation(self, event: Dict):
        """Track trust network evolution"""
        data = event.get('data', {})
        agent1 = data.get('agent1')
        agent2 = data.get('agent2')
        trust_level = data.get('trust_level', 0.5)
        
        self._update_trust_edge(agent1, agent2, trust_level)
        
    def _update_trust_edge(self, agent1: str, agent2: str, weight_delta: float):
        """Update trust network edge weight"""
        if self.trust_network.has_edge(agent1, agent2):
            current = self.trust_network[agent1][agent2]['weight']
            new_weight = max(0, min(1, current + weight_delta))
            self.trust_network[agent1][agent2]['weight'] = new_weight
        else:
            self.trust_network.add_edge(agent1, agent2, weight=0.5 + weight_delta)
            
        # Update trust pairs (strong mutual trust)
        self.metrics['trust_pairs'] = [
            (u, v) for u, v, d in self.trust_network.edges(data=True)
            if d['weight'] > 0.7
        ]
        
    def _process_state_update(self, event: Dict):
        """Process state updates for experiment metrics"""
        data = event.get('data', {})
        entity_type = data.get('type')
        
        if entity_type == 'experiment_metrics':
            properties = data.get('properties', {})
            self._update_time_series(properties)
            
    def _update_time_series(self, metrics: Dict):
        """Update time series data"""
        current_time = time.time() - self.start_time
        self.time_series['timestamps'].append(current_time)
        
        self.time_series['cooperation_rates'].append(
            self.metrics['current_cooperation_rate']
        )
        
        # Calculate trust network density
        if self.trust_network.number_of_nodes() > 1:
            density = nx.density(self.trust_network)
        else:
            density = 0
        self.time_series['trust_density'].append(density)
        
        # Track norm adoption
        total_agents = len(set(h['agent'] for h in self.cooperation_history))
        if total_agents > 0 and self.active_norms:
            avg_adopters = np.mean([len(n['adopters']) for n in self.active_norms])
            adoption_rate = avg_adopters / total_agents
        else:
            adoption_rate = 0
        self.time_series['norm_adoption'].append(adoption_rate)
        
    def calculate_emergence_indicators(self) -> Dict:
        """Calculate indicators of emergent cooperation"""
        indicators = {}
        
        # Pattern stability (low variance = stable)
        if len(self.time_series['cooperation_rates']) > 10:
            recent_rates = self.time_series['cooperation_rates'][-50:]
            indicators['stability'] = 1 / (1 + np.var(recent_rates))
        else:
            indicators['stability'] = 0
            
        # Convergence rate (how fast cooperation spreads)
        if len(self.time_series['cooperation_rates']) > 20:
            rates = self.time_series['cooperation_rates']
            # Calculate slope of cooperation trend
            x = np.arange(len(rates))
            slope, _ = np.polyfit(x, rates, 1)
            indicators['convergence_rate'] = slope
        else:
            indicators['convergence_rate'] = 0
            
        # Network clustering (cooperation clusters)
        if self.trust_network.number_of_nodes() > 3:
            indicators['clustering'] = nx.average_clustering(self.trust_network)
        else:
            indicators['clustering'] = 0
            
        # Communication effectiveness
        if self.metrics['communication_volume'] > 0:
            # Correlation between communication and cooperation
            indicators['communication_impact'] = self.metrics['current_cooperation_rate']
        else:
            indicators['communication_impact'] = 0
            
        self.metrics['emergence_indicators'] = indicators
        return indicators
        
    def detect_strategy_patterns(self) -> Dict:
        """Detect common strategy patterns in agent behavior"""
        patterns = defaultdict(int)
        
        # Analyze recent move sequences
        agent_histories = defaultdict(list)
        for move in list(self.cooperation_history)[-500:]:
            agent_histories[move['agent']].append(move['cooperative'])
            
        for agent, history in agent_histories.items():
            if len(history) < 10:
                continue
                
            # Always Cooperate
            if all(history[-10:]):
                patterns['always_cooperate'] += 1
            # Always Defect
            elif not any(history[-10:]):
                patterns['always_defect'] += 1
            # Tit-for-Tat pattern
            elif self._is_tit_for_tat(agent):
                patterns['tit_for_tat'] += 1
            # Complex/Adaptive
            else:
                patterns['complex'] += 1
                
        self.patterns = patterns
        return patterns
        
    def _is_tit_for_tat(self, agent: str) -> bool:
        """Check if agent follows tit-for-tat pattern"""
        agent_moves = [
            m for m in self.cooperation_history 
            if m['agent'] == agent
        ]
        
        if len(agent_moves) < 5:
            return False
            
        # Check if agent mirrors opponent's previous move
        mirrors = 0
        for i in range(1, len(agent_moves)):
            # Find opponent's previous move
            prev_round = agent_moves[i-1]['round']
            opponent = agent_moves[i]['opponent']
            
            opp_prev = next(
                (m for m in self.cooperation_history 
                 if m['agent'] == opponent and m['round'] == prev_round),
                None
            )
            
            if opp_prev and agent_moves[i]['cooperative'] == opp_prev['cooperative']:
                mirrors += 1
                
        return mirrors / (len(agent_moves) - 1) > 0.7
        
    def generate_summary(self) -> Dict:
        """Generate comprehensive experiment summary"""
        emergence = self.calculate_emergence_indicators()
        patterns = self.detect_strategy_patterns()
        
        summary = {
            'experiment_id': self.experiment_id,
            'duration': time.time() - self.start_time,
            'total_moves': len(self.cooperation_history),
            'final_cooperation_rate': self.metrics['current_cooperation_rate'],
            'trust_pairs_formed': len(self.metrics['trust_pairs']),
            'norms_emerged': self.metrics['norm_count'],
            'communication_volume': self.metrics['communication_volume'],
            'emergence_indicators': emergence,
            'strategy_patterns': dict(patterns),
            'time_series_data': self.time_series
        }
        
        return summary
        
    def save_data(self, filepath: str):
        """Save experiment data to file"""
        summary = self.generate_summary()
        
        with open(filepath, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
            
        print(f"Experiment data saved to {filepath}")


class CooperationVisualizer:
    """Real-time visualization of cooperation dynamics"""
    
    def __init__(self, monitor: CooperationMonitor):
        self.monitor = monitor
        self.fig, self.axes = plt.subplots(2, 2, figsize=(15, 10))
        self.fig.suptitle(f'Cooperation Dynamics - Experiment {monitor.experiment_id}')
        
    def animate(self, frame):
        """Update visualizations in real-time"""
        # Clear axes
        for ax in self.axes.flat:
            ax.clear()
            
        # Plot 1: Cooperation rate over time
        ax1 = self.axes[0, 0]
        if self.monitor.time_series['timestamps']:
            ax1.plot(self.monitor.time_series['timestamps'],
                    self.monitor.time_series['cooperation_rates'], 'b-')
            ax1.fill_between(self.monitor.time_series['timestamps'],
                            self.monitor.time_series['cooperation_rates'],
                            alpha=0.3)
        ax1.set_xlabel('Time (seconds)')
        ax1.set_ylabel('Cooperation Rate')
        ax1.set_title('Cooperation Evolution')
        ax1.set_ylim([0, 1])
        ax1.grid(True, alpha=0.3)
        
        # Plot 2: Trust network
        ax2 = self.axes[0, 1]
        if self.monitor.trust_network.number_of_nodes() > 0:
            pos = nx.spring_layout(self.monitor.trust_network)
            
            # Draw nodes
            nx.draw_networkx_nodes(self.monitor.trust_network, pos, ax=ax2,
                                 node_size=300, node_color='lightblue')
            
            # Draw edges with width based on trust
            edges = self.monitor.trust_network.edges(data=True)
            for u, v, d in edges:
                weight = d.get('weight', 0.5)
                nx.draw_networkx_edges(self.monitor.trust_network, pos,
                                      [(u, v)], ax=ax2,
                                      width=weight*3,
                                      alpha=weight)
            
            # Draw labels
            nx.draw_networkx_labels(self.monitor.trust_network, pos, ax=ax2,
                                   font_size=8)
        ax2.set_title('Trust Network')
        ax2.axis('off')
        
        # Plot 3: Strategy distribution
        ax3 = self.axes[1, 0]
        if self.monitor.patterns:
            strategies = list(self.monitor.patterns.keys())
            counts = list(self.monitor.patterns.values())
            colors = ['green', 'red', 'blue', 'orange']
            ax3.bar(strategies, counts, color=colors[:len(strategies)])
        ax3.set_xlabel('Strategy Type')
        ax3.set_ylabel('Agent Count')
        ax3.set_title('Strategy Distribution')
        ax3.tick_params(axis='x', rotation=45)
        
        # Plot 4: Emergence indicators
        ax4 = self.axes[1, 1]
        indicators = self.monitor.calculate_emergence_indicators()
        if indicators:
            labels = list(indicators.keys())
            values = list(indicators.values())
            
            # Radar chart
            angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False)
            values = np.concatenate((values, [values[0]]))
            angles = np.concatenate((angles, [angles[0]]))
            
            ax4.plot(angles, values, 'o-', linewidth=2)
            ax4.fill(angles, values, alpha=0.25)
            ax4.set_xticks(angles[:-1])
            ax4.set_xticklabels(labels)
            ax4.set_ylim([0, 1])
        ax4.set_title('Emergence Indicators')
        
        plt.tight_layout()
        
    def start_live_visualization(self):
        """Start live visualization"""
        ani = animation.FuncAnimation(self.fig, self.animate, 
                                    interval=1000, cache_frame_data=False)
        plt.show()
        return ani


class ExperimentRunner:
    """Orchestrates and monitors cooperation experiments"""
    
    def __init__(self, experiment_type: str, **kwargs):
        self.experiment_id = f"exp_{int(time.time())}"
        self.experiment_type = experiment_type
        self.params = kwargs
        self.monitor = CooperationMonitor(self.experiment_id)
        self.visualizer = CooperationVisualizer(self.monitor)
        
    async def run_experiment(self):
        """Run the experiment with monitoring"""
        print(f"Starting experiment {self.experiment_id}")
        print(f"Type: {self.experiment_type}")
        print(f"Parameters: {self.params}")
        
        # Start KSI workflow
        await self._start_ksi_workflow()
        
        # Start monitoring
        monitor_task = asyncio.create_task(self._monitor_events())
        
        # Start visualization (optional)
        if self.params.get('visualize', True):
            self.visualizer.start_live_visualization()
            
        # Wait for experiment completion
        await monitor_task
        
        # Generate final report
        self._generate_report()
        
    async def _start_ksi_workflow(self):
        """Start the KSI experiment workflow"""
        import subprocess
        
        cmd = [
            'ksi', 'send', 'workflow:execute',
            '--workflow', 'cooperation_experiment_orchestrator',
            '--vars', json.dumps({
                'experiment_id': self.experiment_id,
                'experiment_type': self.experiment_type,
                **self.params
            })
        ]
        
        subprocess.Popen(cmd)
        
    async def _monitor_events(self):
        """Monitor KSI events in real-time"""
        # This would connect to KSI's event stream
        # For now, simulate with test data
        
        for _ in range(self.params.get('rounds', 1000)):
            # Simulate events
            event = self._generate_test_event()
            self.monitor.process_event(event)
            await asyncio.sleep(0.1)
            
    def _generate_test_event(self) -> Dict:
        """Generate test events for development"""
        import random
        
        event_types = ['game:move', 'message:send', 'trust:formed']
        event_type = random.choice(event_types)
        
        if event_type == 'game:move':
            return {
                'event': 'game:move',
                'data': {
                    'agent_id': f'agent_{random.randint(1, 10)}',
                    'opponent_id': f'agent_{random.randint(1, 10)}',
                    'move': random.choice(['C', 'D']),
                    'round': random.randint(1, 100)
                }
            }
        elif event_type == 'message:send':
            return {
                'event': 'message:send',
                'data': {
                    'sender': f'agent_{random.randint(1, 10)}',
                    'receiver': f'agent_{random.randint(1, 10)}',
                    'message': random.choice([
                        "Let's cooperate",
                        "I will defect",
                        "Trust me"
                    ])
                }
            }
        else:
            return {
                'event': 'trust:formed',
                'data': {
                    'agent1': f'agent_{random.randint(1, 10)}',
                    'agent2': f'agent_{random.randint(1, 10)}',
                    'trust_level': random.random()
                }
            }
            
    def _generate_report(self):
        """Generate final experiment report"""
        summary = self.monitor.generate_summary()
        
        # Save data
        data_file = f"var/experiments/{self.experiment_id}/data.json"
        self.monitor.save_data(data_file)
        
        # Generate markdown report
        report = f"""
# Experiment Report: {self.experiment_id}

## Summary
- **Type**: {self.experiment_type}
- **Duration**: {summary['duration']:.2f} seconds
- **Total Moves**: {summary['total_moves']}
- **Final Cooperation Rate**: {summary['final_cooperation_rate']:.2%}

## Key Findings
- **Trust Pairs Formed**: {summary['trust_pairs_formed']}
- **Norms Emerged**: {summary['norms_emerged']}
- **Communication Volume**: {summary['communication_volume']}

## Emergence Indicators
{json.dumps(summary['emergence_indicators'], indent=2)}

## Strategy Distribution
{json.dumps(summary['strategy_patterns'], indent=2)}

## Data Location
- Raw data: `{data_file}`
- Visualizations: `var/experiments/{self.experiment_id}/plots/`
"""
        
        report_file = f"docs/experiments/{self.experiment_id}_report.md"
        with open(report_file, 'w') as f:
            f.write(report)
            
        print(f"Report generated: {report_file}")


def main():
    """Run cooperation dynamics experiments"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Run cooperation experiments')
    parser.add_argument('--type', choices=['communication_ladder', 'component_ablation', 
                                          'multi_model', 'norm_emergence'],
                       default='communication_ladder')
    parser.add_argument('--population', type=int, default=20)
    parser.add_argument('--rounds', type=int, default=1000)
    parser.add_argument('--visualize', action='store_true')
    
    args = parser.parse_args()
    
    runner = ExperimentRunner(
        experiment_type=args.type,
        population_size=args.population,
        rounds=args.rounds,
        visualize=args.visualize
    )
    
    asyncio.run(runner.run_experiment())


if __name__ == "__main__":
    main()