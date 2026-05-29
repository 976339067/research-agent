import json
import os
import sys
from openai import OpenAI

from dotenv import load_dotenv
from ddgs import DDGS

load_dotenv()  # 这行必须在 os.getenv 之前

# 从环境变量获取 API Key 和 Base URL（安全，不会泄露到 git）
ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY")
ZHIPU_BASE_URL = os.getenv("ZHIPU_BASE_URL")

# 打印读入的变量，确定值没有问题
#print("ZHIPU_API_KEY:", ZHIPU_API_KEY)
#print("ZHIPU_BASE_URL:", ZHIPU_BASE_URL)

# 环境变量检查：缺失时给出明确提示并退出
if not ZHIPU_API_KEY:
    print("错误：未设置环境变量 ZHIPU_API_KEY")
    print("请执行：export ZHIPU_API_KEY='你的密钥'")
    sys.exit(1)
if not ZHIPU_BASE_URL:
    print("错误：未设置环境变量 ZHIPU_BASE_URL")
    print("请执行：export ZHIPU_BASE_URL='https://open.bigmodel.cn/api/paas/v4/'")
    sys.exit(1)

# 安全打印：只显示是否已设置，不暴露完整密钥
print("ZHIPU_API_KEY 已设置:", ZHIPU_API_KEY[:8] + "..." if len(ZHIPU_API_KEY) > 8 else "***")
print("ZHIPU_BASE_URL:", ZHIPU_BASE_URL)

# 创建客户端，使用环境变量中的 API Key
client = OpenAI(
    api_key=ZHIPU_API_KEY,
    base_url=ZHIPU_BASE_URL
)



# ==================== 工具函数 ====================
def web_search(query: str, max_results: int = 5) -> str:
    """使用 DuckDuckGo 搜索网页"""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"搜索失败：{str(e)}"
# ==================== 工具定义 ====================
tools = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "搜索网页获取最新信息。当需要实时数据或不在知识库中的信息时使用此工具",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词，尽量具体明确"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "返回结果数量，默认5",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        }
    }
]

# ==================== Agent 函数 ====================
def run_agent(user_message: str, max_iterations: int = 5) -> str:
    """运行 Agent，支持 function calling（支持多轮工具调用）"""
    messages = [{"role": "user", "content": user_message}]
    print(f"[DEBUG] 开始 Agent 会话，用户消息: {user_message}")

    for iteration in range(max_iterations):
        print(f"\n[DEBUG] === 迭代 {iteration + 1}/{max_iterations} ===")

        # 调用 LLM 前
        print(f"[DEBUG] 发送消息数: {len(messages)}")

        response = client.chat.completions.create(
            model="GLM-4.7-Flash",
            messages=messages,
            tools=tools
        )

        assistant_message = response.choices[0].message
        messages.append(assistant_message)

        # 调用 LLM 后
        print(f"[DEBUG] LLM 返回 - tool_calls: {bool(assistant_message.tool_calls)}")
        if assistant_message.tool_calls:
            print(f"[DEBUG] tool_calls 数量: {len(assistant_message.tool_calls)}")
            for i, tc in enumerate(assistant_message.tool_calls):
                print(f"[DEBUG]   tool_call[{i}]: {tc.function.name}({tc.function.arguments})")
        else:
            content_preview = assistant_message.content[:100] if assistant_message.content else "empty"
            print(f"[DEBUG] content: {content_preview}...")
            if hasattr(assistant_message, 'reasoning_content') and assistant_message.reasoning_content:
                reasoning_preview = assistant_message.reasoning_content[:100]
                print(f"[DEBUG] reasoning_content: {reasoning_preview}...")

        # 无工具调用
        if not assistant_message.tool_calls:
            print("[DEBUG] 无工具调用，返回最终回复")
            if hasattr(assistant_message, 'reasoning_content') and assistant_message.reasoning_content:
                return assistant_message.reasoning_content
            return assistant_message.content or ""

        # 执行工具调用
        for tool_call in assistant_message.tool_calls:
            function_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)

            # 调用工具前
            print(f"[DEBUG] 调用工具: {function_name}, 参数: {arguments}")

            if function_name == "web_search":
                result = web_search(**arguments)

                print("result:", result)
                # 调用工具后
                print(f"[DEBUG] 工具返回 - 长度: {len(result)}, 失败: {result.startswith('搜索失败：')}")
                if result.startswith("搜索失败："):
                    print(f"[DEBUG] 搜索失败详情: {result}")
                    return f"抱歉，搜索遇到问题：{result}"
                else:
                    result_preview = result[:200] if len(result) > 200 else result
                    print(f"[DEBUG] 结果预览: {result_preview}...")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })

    print("[DEBUG] 达到最大迭代次数")
    return "达到最大迭代次数，未能完成"

# ==================== 测试函数 ====================
def test_llm_connectivity():
    """测试 LLM 连通性"""
    print("\n=== 测试 LLM 连通性 ===")
    try:
        response = client.chat.completions.create(
            model="GLM-4.7-Flash",
            messages=[{"role": "user", "content": "你好，请用一句话介绍你自己"}]
        )
        print(response.choices[0].message.content)
        return True
    except Exception as e:
        print(f"API 调用失败：{e}")
        return False

def test_web_search():
    """测试 web_search 工具"""
    print("\n=== 测试 web_search 工具 ===")
    result = web_search("AI Agent 最新发展", max_results=3)
    print(result)

def test_function_calling():
    """测试 function calling"""
    print("\n=== 测试 Function Calling ===")
    result = run_agent("搜索一下 AI Agent 的最新发展")
    #result = run_agent("搜索一下 当前国家数量（不包括地区，联合国承认的国家）")
    print(f"\nAgent 回复:\n{result}")

def run_tests():
    """运行所有测试"""
    #test_llm_connectivity()
    #test_web_search()
    test_function_calling()

if __name__ == "__main__":
    run_tests()
