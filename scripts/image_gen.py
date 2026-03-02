#!/usr/bin/env python3
"""
小红书配图生成器
使用 Seedream 5.0 API 生成图片
"""

import os
import requests
import time
from pathlib import Path

# 配置
SEEDREAM_API_URL = os.environ.get('SEEDREAM_API_URL', 'https://ark.cn-beijing.volces.com/api/v3/images/generations')
SEEDREAM_MODEL = os.environ.get('SEEDREAM_MODEL', 'doubao-seedream-5-0-260128')
SEEDREAM_API_KEY = os.environ.get('SEEDREAM_API_KEY', '')
PROXY = os.environ.get('HTTP_PROXY') or os.environ.get('HTTPS_PROXY') or os.environ.get('http_proxy') or os.environ.get('https_proxy', 'http://127.0.0.1:8118')


def generate_image(prompt, output_path=None, size='2k'):
    """
    使用 Seedream 5.0 生成图片
    
    Args:
        prompt: 图片描述
        output_path: 输出路径（可选）
        size: 分辨率，默认 2k (2048x2048)
    
    Returns:
        图片路径或 None
    """
    if not output_path:
        output_path = f'/tmp/seedream_{int(time.time())}.jpg'
    
    headers = {
        'Authorization': f'Bearer {SEEDREAM_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    data = {
        'model': SEEDREAM_MODEL,
        'prompt': prompt,
        'size': size,
        'n': 1
    }
    
    proxies = {'http': PROXY, 'https': PROXY} if PROXY else None
    
    print(f'Generating image with prompt: {prompt[:50]}...')
    
    # 发起请求
    resp = requests.post(SEEDREAM_API_URL, headers=headers, json=data, timeout=60, proxies=proxies)
    if resp.status_code != 200:
        print(f'Error: {resp.status_code} {resp.text}')
        return None
    
    result = resp.json()
    task_id = result.get('data', [{}])[0].get('id')
    if not task_id:
        print(f'No task ID: {result}')
        return None
    
    # 轮询结果
    for i in range(60):
        time.sleep(2)
        status_url = f'https://ark.cn-beijing.volces.com/api/v3/tasks/{task_id}'
        status_r = requests.get(status_url, headers=headers, proxies=proxies)
        status = status_r.json()
        
        if status.get('status') == 'succeeded':
            image_url = status['data']['output']['url']
            # 下载图片
            img_resp = requests.get(image_url, proxies=proxies)
            with open(output_path, 'wb') as f:
                f.write(img_resp.content)
            print(f'Image saved to: {output_path}')
            return output_path
        elif status.get('status') == 'failed':
            print(f'Failed: {status}')
            return None
    
    print('Timeout waiting for image')
    return None


def main():
    import argparse
    parser = argparse.ArgumentParser(description='小红书配图生成')
    parser.add_argument('--prompt', '-p', required=True, help='图片描述')
    parser.add_argument('--output', '-o', help='输出路径')
    parser.add_argument('--size', '-s', default='2k', help='分辨率 (1k, 2k, 4k)')
    
    args = parser.parse_args()
    result = generate_image(args.prompt, args.output, args.size)
    if result:
        print(f'Success: {result}')
    else:
        print('Failed')


if __name__ == '__main__':
    main()
