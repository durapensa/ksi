import asyncio
from ksi_client import EventClient

async def check_composition():
    async with EventClient() as client:
        # Get the base_single_agent composition
        result = await client.send_single('composition:get', {'name': 'base_single_agent'})
        
        print(f"Get result keys: {list(result.keys())}")
        if 'error' in result:
            print(f"ERROR getting composition: {result['error']}")
        
        if 'composition' in result:
            comp_data = result['composition']
            print(f"\nComposition type: {comp_data.get('type')}")
            print("Components in base_single_agent:")
            for comp in comp_data.get('components', []):
                print(f"  - {comp['name']}")
                if comp['name'] == 'system_context' and 'inline' in comp:
                    print(f"    System prompt: {comp['inline'].get('prompt', '')[:100]}...")
        
        # Try composition:compose first
        compose_result = await client.send_single('composition:compose', {
            'name': 'base_single_agent',
            'type': 'profile'
        })
        
        print(f"\nCompose result keys: {list(compose_result.keys())}")
        if 'error' in compose_result:
            print(f"ERROR in compose: {compose_result['error']}")
        
        # Check what's in the composition
        if 'composition' in compose_result:
            composition = compose_result['composition']
            print(f"\nComposition keys: {list(composition.keys())}")
            
            # Check for system_context
            if 'system_context' in composition:
                sys_ctx = composition['system_context']
                print(f"system_context type: {type(sys_ctx)}")
                if isinstance(sys_ctx, dict):
                    print(f"system_context keys: {list(sys_ctx.keys())}")
                    if 'prompt' in sys_ctx:
                        print(f"Found prompt in system_context: {sys_ctx['prompt'][:100]}...")
                    if 'inline' in sys_ctx:
                        print(f"inline keys: {list(sys_ctx['inline'].keys())}")
                        if 'prompt' in sys_ctx['inline']:
                            print(f"Found prompt in inline: {sys_ctx['inline']['prompt'][:100]}...")

asyncio.run(check_composition())