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

def read_file(file_path: str, encoding: str = "utf-8") -> str:
    """读取本地文件内容"""
    try:
        # 安全检查：限制可访问的目录
        script_dir = os.path.dirname(os.path.abspath(__file__))
        allowed_dirs = [os.path.join(script_dir, "data")]
        full_path = os.path.abspath(file_path)

        # 检查路径是否在允许的目录中（防止路径遍历攻击）
        is_allowed = False
        for allowed_dir in allowed_dirs:
            # 确保路径匹配且下一字符是路径分隔符或路径结束
            if full_path == allowed_dir or full_path.startswith(allowed_dir + os.sep):
                is_allowed = True
                break

        if not is_allowed:
            return f"错误：不允许访问路径 {file_path}（仅限脚本目录下的 data 子目录）"

        # 文件大小限制（1MB）
        file_size = os.path.getsize(full_path)
        if file_size > 1024 * 1024:
            return f"错误：文件过大 ({file_size} 字节)，超过 1MB 限制"

        with open(full_path, 'r', encoding=encoding) as f:
            content = f.read()
            return f"成功读取 {file_path} ({len(content)} 字符)\n\n{content}"
    except FileNotFoundError:
        return f"错误：文件不存在 {file_path}"
    except UnicodeDecodeError:
        return f"错误：编码失败，尝试其他编码如 gbk 或 utf-8-sig"
    except Exception as e:
        return f"读取失败：{str(e)}"
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
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "读取本地文件内容。支持 txt, md, json, csv 等文本文件。仅限脚本目录下的 data 子目录，文件大小限制 1MB。",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "文件路径，可以是相对路径或绝对路径"
                    },
                    "encoding": {
                        "type": "string",
                        "description": "文件编码，默认 utf-8",
                        "default": "utf-8"
                    }
                },
                "required": ["file_path"]
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

            elif function_name == "read_file":
                result = read_file(**arguments)

                # 调用工具后
                print(f"[DEBUG] 工具返回 - 长度: {len(result)}, 失败: {result.startswith('错误：')}")
                if result.startswith("错误："):
                    print(f"[DEBUG] 读取失败详情: {result}")
                    return f"抱歉，读取遇到问题：{result}"
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

def test_read_file():
    """测试 read_file 工具"""
    print("\n=== 测试 read_file 工具 ===")

    # 先创建测试文件
    test_file = "test_data.txt"
    test_content = "随着全球碳中和目标的推进，固态电池被认为是下一代电动汽车动力电池的核心方向。与传统锂离子电池相比，固态电池用固态电解质替代了易燃的液态电解质，理论上可将能量密度提升至500Wh/kg以上，同时大幅降低热失控风险。根据行业报告，2025年全球固态电池市场规模约为12亿美元，预计到2030年将增长至72亿美元，年复合增长率达43%。然而，固态电池仍面临两大技术瓶颈：一是固态电解质与电极之间的界面阻抗较高，影响快充性能；二是制造成本居高不下，目前约为液态锂电池的4-6倍。尽管丰田、宁德时代等头部企业已宣布2027年前后实现小规模量产，但大规模商业化应用可能仍需五年以上时间。总体来看，固态电池前景广阔，但技术突破和降本路径仍是行业关注的焦点。"
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write(test_content)

    print(f"已创建测试文件: {test_file}")

    # 直接测试 read_file 函数
    result = read_file(test_file)
    print(f"\n直接调用 read_file():\n{result}")

    # 测试通过 Agent 调用
    print("\n--- 通过 Agent 调用 ---")
    result = run_agent(f"读取 {test_file} 并总结内容")
    print(f"\nAgent 回复:\n{result}")

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
    #test_function_calling()
    test_read_file()

if __name__ == "__main__":
    run_tests()
