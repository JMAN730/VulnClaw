#!/usr/bin/env python3
"""Test script to demonstrate streaming output visual effect."""

import asyncio
import sys
import io

from rich.console import Console

# Import our streaming components
sys.path.insert(0, '/workspace')

from vulnclaw.cli.main import TerminalStreamSink


async def simulate_streaming_output():
    """模拟流式输出效果"""
    # Create console for output
    console = Console(file=sys.stdout, force_terminal=True, force_interactive=True)
    
    # Create sink
    sink = TerminalStreamSink(console, show_thinking=True)
    
    console.print("\n" + "="*60)
    console.print("[bold cyan]VulnClaw 流式输出演示")
    console.print("="*60 + "\n")
    
    # Test 1: Basic thinking + content
    console.print("[dim]Test 1: 思考过程 + 正文输出[/]")
    sink.on_status("Thinking...")
    await asyncio.sleep(0.5)
    
    sink.on_thinking_token("分析目标系统...")
    await asyncio.sleep(0.3)
    sink.on_thinking_token("检查端口状态...")
    await asyncio.sleep(0.3)
    sink.on_thinking_token("发现潜在漏洞...")
    await asyncio.sleep(0.3)
    
    sink.on_content_token("目标系统 ")
    await asyncio.sleep(0.1)
    sink.on_content_token("192.168.1.100 ")
    await asyncio.sleep(0.1)
    sink.on_content_token("存在 ")
    await asyncio.sleep(0.1)
    sink.on_content_token("SQL注入")
    await asyncio.sleep(0.1)
    sink.on_content_token("漏洞")
    await asyncio.sleep(0.1)
    
    sink.on_stream_end()
    console.print("\n")
    
    # Test 2: Tool call
    console.print("[dim]Test 2: 工具调用[/]")
    sink.on_tool_call("nmap_scan", '{"target": "192.168.1.100", "ports": "1-1000"}')
    await asyncio.sleep(0.5)
    sink.on_tool_result("发现开放端口: 22 (SSH), 80 (HTTP), 443 (HTTPS), 3306 (MySQL)")
    sink.on_stream_end()
    console.print("\n")
    
    # Test 3: Show thinking disabled
    console.print("[dim]Test 3: 隐藏思考过程 (show_thinking=False)[/]")
    sink2 = TerminalStreamSink(console, show_thinking=False)
    sink2.on_status("Thinking...")
    await asyncio.sleep(0.5)
    
    sink2.on_thinking_token("这个思考不会显示")
    await asyncio.sleep(0.3)
    
    sink2.on_content_token("直接输出 ")
    await asyncio.sleep(0.1)
    sink2.on_content_token("结果")
    sink2.on_stream_end()
    
    console.print("\n" + "="*60)
    console.print("[bold green]演示完成!")
    console.print("="*60)


if __name__ == "__main__":
    asyncio.run(simulate_streaming_output())
