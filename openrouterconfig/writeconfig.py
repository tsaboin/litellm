import requests
import yaml
import os
from pathlib import Path


def fetch_openrouter_models():
    """Fetch all models from OpenRouter API"""
    url = "https://openrouter.ai/api/v1/models"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()['data']


def fetch_openclaw_models():
    """Fetch all models from Openclaw API"""
    url = "https://quadri.deleodufuye.com/v1/models"
    token = os.environ.get('OPENCLAW_TOKEN')
    if not token:
        raise ValueError("OPENCLAW_TOKEN environment variable is not set")
    headers = {
        "Authorization": f"Bearer {token}",
        "x-openclaw-scopes": "operator.write" 
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()['data']


def create_openrouter_model_entry(model):
    """Convert OpenRouter model to config format"""
    model_id = model['id']
    model_name = model['name']

    mode = "completion"
    if 'architecture' in model and 'output_modalities' in model['architecture']:
        output_modalities = model['architecture']['output_modalities']
        if 'image' in output_modalities:
            mode = "image_generation"

    entry = {
        'model_name': f"{model_name}",
        'litellm_params': {
            'model': f"openrouter/{model_id}",
            'api_key': 'os.environ/OPENROUTER_API_KEY',
            'drop_params': True,
            'allowed_openai_params': ['reasoning_effort']
        },
        'model_info': {
            'id': model_id,
            'mode': mode,
            'description': f"{model['name']} from OpenRouter. {model['description']}",
            'max_tokens': model['context_length']
        }
    }

    if 'pricing' in model:
        if 'prompt' in model['pricing']:
            original_price = float(model['pricing']['prompt'])
            marked_up_price = original_price * 1.15
            entry['litellm_params']['input_cost_per_token'] = str(marked_up_price)
        if 'completion' in model['pricing']:
            original_price = float(model['pricing']['completion'])
            marked_up_price = original_price * 1.15
            entry['litellm_params']['output_cost_per_token'] = str(marked_up_price)

    return entry


def create_openclaw_model_entry(model):
    """Convert Openclaw model to config format"""
    model_id = model['id']  # e.g., "openclaw/dele"

    # 1. Remove the "openclaw/" prefix explicitly
    # If model_id is "openclaw/dele", this results in "dele"  
    if model_id.startswith("openclaw/"):
        agent_id_raw = model_id.replace("openclaw/", "", 1)
    else:
        agent_id_raw = model_id

    # 2. Title case the agent ID (e.g., "dele" -> "Dele")
    agent_id_title = agent_id_raw.title()

    # 3. Create the new model_name
    model_name = f"FortisAgent: {agent_id_title}"

    entry = {
        'model_name': model_name,
        'litellm_params': {
            # Keep 'openai/' prefix so LiteLLM knows how to handle the request
            'model': f"openai/{model_id}",
            'api_base': 'https://quadri.deleodufuye.com/v1',
            'api_key': 'os.environ/OPENCLAW_TOKEN',
            'drop_params': True,
            'allowed_openai_params': ['user'],
            'extra_headers': {
                'x-openclaw-scopes': 'operator.write'
            }
        },
        'model_info': {
            'id': model_id,
            'mode': 'responses',
            'description': f"{model_name} from Openclaw."
        }
    }

    if 'context_length' in model:
        entry['model_info']['max_tokens'] = model['context_length']

    return entry


def generate_config():
    """Generate complete config.yaml"""
    config = {
        'general_settings': {
            'user_header_mappings': [
                {
                    'header_name': 'X-OpenWebUI-User-Email',
                    'litellm_user_role': 'customer'
                },
                {
                    'header_name': 'X-OpenWebUI-User-Email',
                    'litellm_user_role': 'internal_user'
                }
            ],
            'store_model_in_db': True,
            'store_prompts_in_spend_logs': True,
            'maximum_spend_logs_retention_period': '7d',
        },
        'litellm_settings': {
            'callbacks': ['smtp_email', 'langfuse'],
            'allowed_openai_params': ['reasoning_effort','user','pronunciation_dictionary_locators'],
            'drop_params': True,
            'cache': True,
            'cache_params': {
                'type': 'local'
            }
        },
        'model_list': []
    }

    # Fetch and process OpenRouter models
    openrouter_models = fetch_openrouter_models()
    openrouter_entries = [create_openrouter_model_entry(model) for model in openrouter_models]

    # Fetch and process Openclaw models
    openclaw_models = fetch_openclaw_models()
    openclaw_entries = [create_openclaw_model_entry(model) for model in openclaw_models]

    config['model_list'] = openrouter_entries + openclaw_entries

    return config


def save_config(config):
    """Save config to YAML file"""
    output_path = Path(__file__).parent / 'proxy_config.yaml'

    with open(output_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    print(f"Config saved to {output_path}")
    print(f"Total models: {len(config['model_list'])}")


if __name__ == '__main__':
    config = generate_config()
    save_config(config)
