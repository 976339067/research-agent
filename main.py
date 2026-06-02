import json
import os
import subprocess
import sys
from openai import OpenAI

from dotenv import load_dotenv
from ddgs import DDGS

load_dotenv()  # 这行必须在 os.getenv 之前

# 从环境变量获取 API Key 和 Base URL（安全，不会泄露到 git）
ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY")
ZHIPU_BASE_URL = os.getenv("ZHIPU_BASE_URL")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# 打印读入的变量，确定值没有问题
#print("ZHIPU_API_KEY:", ZHIPU_API_KEY)
#print("ZHIPU_BASE_URL:", ZHIPU_BASE_URL)
#print("TAVILY_API_KEY:", TAVILY_API_KEY)

# 环境变量检查：缺失时给出明确提示并退出
if not ZHIPU_API_KEY:
    print("错误：未设置环境变量 ZHIPU_API_KEY")
    print("请执行：export ZHIPU_API_KEY='你的密钥'")
    sys.exit(1)
if not ZHIPU_BASE_URL:
    print("错误：未设置环境变量 ZHIPU_BASE_URL")
    print("请执行：export ZHIPU_BASE_URL='https://open.bigmodel.cn/api/paas/v4/'")
    sys.exit(1)
if not TAVILY_API_KEY:
    print("错误：未设置环境变量 TAVILY_API_KEY")
    print("请执行：export TAVILY_API_KEY='你的密钥'")
    sys.exit(1)

# 安全打印：只显示是否已设置，不暴露完整密钥
print("ZHIPU_API_KEY 已设置:", ZHIPU_API_KEY[:8] + "..." if len(ZHIPU_API_KEY) > 8 else "***")
print("ZHIPU_BASE_URL:", ZHIPU_BASE_URL)
print("TAVILY_API_KEY 已设置:", TAVILY_API_KEY[:8] + "..." if len(TAVILY_API_KEY) > 8 else "***")

# 创建客户端，使用环境变量中的 API Key
client = OpenAI(
    api_key=ZHIPU_API_KEY,
    base_url=ZHIPU_BASE_URL
)



# ==================== 工具函数 ====================
def web_search_with_ddgs(query: str, max_results: int = 5) -> str:
    """使用 DuckDuckGo 搜索网页"""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"搜索失败：{str(e)}"

def web_search_with_tavily(query: str, max_results: int = 5) -> str:
    """使用 Tavily 搜索网页"""
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
        response = client.search(
            query=query,
            max_results=max_results,
            search_depth="basic"
        )
        return json.dumps(response, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"搜索失败：{str(e)}"

def web_search(query: str, max_results: int = 5) -> str:
    """使用 Tavily 搜索网页"""
    return web_search_with_tavily(query, max_results)

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

def save_file(file_path: str, content: str, encoding: str = "utf-8", mode: str = "w") -> str:
    """保存内容到文件"""
    try:
        # 安全检查：限制可写入的目录
        script_dir = os.path.dirname(os.path.abspath(__file__))
        allowed_dirs = [
            os.path.join(script_dir, "output"),
            os.path.join(script_dir, "reports")
        ]
        full_path = os.path.abspath(file_path)

        # 检查路径是否在允许的目录中
        is_allowed = False
        for allowed_dir in allowed_dirs:
            if full_path == allowed_dir or full_path.startswith(allowed_dir + os.sep):
                is_allowed = True
                break

        if not is_allowed:
            return f"错误：不允许写入路径 {file_path}（仅限 output/ 和 reports/ 目录）"

        # 自动创建目录
        dir_name = os.path.dirname(full_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)

        # 写入文件
        with open(full_path, mode, encoding=encoding) as f:
            f.write(content)

        return f"成功保存到 {file_path} ({len(content)} 字符)"

    except Exception as e:
        return f"保存失败：{str(e)}"

def execute_python(
    code_str: str = None,
    script_file: str = None,
    input_path: str = None,
    output_path: str = None,
    timeout: int = 30
) -> str:
    """
    在 Docker 容器中安全地执行 Python 代码进行数据处理。

    ══════════════════════════════════════════════════════════════════════════════
    设计目的 (DESIGN PURPOSE)
    ══════════════════════════════════════════════════════════════════════════════

    本函数为研究助手 Agent 提供安全的代码执行能力，解决以下问题：

    1. 核心问题 (WHY - 为什么需要)
       - 用户需要数据处理、计算分析、格式转换等计算任务
       - 直接在主机执行 Python 代码存在安全风险（文件访问、系统调用等）
       - 需要一种既安全又灵活的代码执行方式

    2. 目标用户 (WHO - 谁使用)
       - 主要使用者：研究助手 Agent（LLM）代表用户执行代码
       - 最终受益者：通过自然语言描述需求的研究人员
       - 使用方式：Agent 通过 Function Calling 自动调用此函数

    3. 应用场景 (WHEN & WHERE - 何时何地)
       - 何时：当用户请求需要计算、分析、处理数据的任务时
       - 何地：在隔离的 Docker 容器中执行，与主机环境完全隔离

    4. 解决方案 (WHAT - 是什么)
       - 使用 Docker 容器技术实现代码沙箱执行
       - 通过严格的资源限制和安全配置保护主机
       - 提供简单易用的接口，支持代码字符串和脚本文件两种方式

    5. 安全隔离 (HOW - 如何实现)
       - 网络隔离：容器无法访问网络，防止数据泄露
       - 资源限制：256MB 内存、单核 CPU，防止资源耗尽
       - 权限控制：非 root 用户、禁止提权
       - 文件隔离：只能访问指定的 data/（读）和 output/（写）目录

    ══════════════════════════════════════════════════════════════════════════════

    功能说明：
    - 使用 Docker 容器隔离执行环境，确保安全性
    - 支持两种代码传递方式：字符串代码或脚本文件
    - 支持文件读写操作（需指定 input_path/output_path）
    - 限制资源使用：内存 256MB、单核 CPU、无网络访问

    何时使用：
    - 数学计算和统计分析
    - 字符串处理和数据转换
    - 文件内容处理（配合 input_path/output_path）
    - 数据分析和格式转换

    何时不使用：
    - 需要网络操作的任务（容器已禁用网络）
    - 需要长时间运行的计算（受 timeout 限制）
    - 需要访问系统资源或敏感文件
    - 处理超大数据（受内存限制）

    参数：
        code_str (str, optional): Python 代码字符串。与 script_file 二选一。
                               用于简单计算、数据处理等场景。
                               示例: "print(sum(range(1, 101)))"

        script_file (str, optional): Python 脚本文件路径。与 code_str 二选一。
                                 脚本必须存放在 data/ 目录下。
                                 用于复杂处理、已有脚本等场景。
                                 示例: "process_data.py"

        input_path (str, optional): 输入文件路径。文件必须在 data/ 目录下。
                                    代码中通过 /app/input/{filename} 访问。
                                    示例: "data/input.txt" → 代码中用 /app/input/input.txt

        output_path (str, optional): 输出文件路径。文件将保存到 output/ 目录。
                                     代码中通过 /app/output/{filename} 写入。
                                     示例: "output/result.txt" → 代码中用 /app/output/result.txt

        timeout (int, optional): 执行超时时间（秒）。默认 30 秒。
                                超时后容器将被强制终止。

    返回：
        str: 执行结果字符串
            - 成功时：返回标准输出内容
            - 失败时：返回错误信息（包含原因和详情）
            - 超时时：返回超时提示
            - 无输出时：返回"执行成功，无输出"

    用法示例：

    示例1: 简单数学计算
        execute_python(code_str="print(sum(range(1, 101)))")
        # 返回: "执行成功\\n\\n输出:\\n5050"

    示例2: 字符串处理
        execute_python(code_str='text="Hello"; print(text.upper())')
        # 返回: "执行成功\\n\\n输出:\\nHELLO"

    示例3: 读取文件并处理
        execute_python(
            code_str='''
with open('/app/input/data.txt') as f:
    lines = f.readlines()
print(f"行数: {len(lines)}")
''',
            input_path="data/data.txt"
        )

    示例4: 处理并保存结果
        execute_python(
            code_str='''
import json
with open('/app/input/data.json') as f:
    data = json.load(f)
result = {'count': len(data), 'sum': sum(data)}
with open('/app/output/result.json', 'w') as f:
    json.dump(result, f)
print("处理完成")
''',
            input_path="data/data.json",
            output_path="output/result.json"
        )

    示例5: 使用脚本文件
        execute_python(
            script_file="analyzer.py",
            input_path="data/raw.txt",
            output_path="output/analyzed.txt"
        )

    安全特性：
    - 容器网络隔离（--network none）
    - 内存限制 256MB（--memory 256m）
    - 单核 CPU 限制（--cpus 1）
    - 非 root 用户运行（--user nobody）
    - 禁止提权（--security-opt=no-new-privileges）
    - 只读挂载输入目录（:ro）
    - 读写挂载输出目录（:rw）

    注意事项：
    - Docker 必须已安装并运行
    - python:3.13-slim 镜像会自动拉取（首次运行时）
    - 代码执行时间超过 timeout 将被强制终止
    - 输出内容大小建议控制在合理范围内
    """
    import subprocess

    # ========== 参数验证 ==========
    if not code_str and not script_file:
        return "错误：必须提供 code_str 或 script_file 参数"
    if code_str and script_file:
        return "错误：code_str 和 script_file 只能提供一个"

    try:
        # ========== 获取项目路径 ==========
        script_dir = os.path.dirname(os.path.abspath(__file__))

        # ========== 构建 Docker 基础命令 ==========
        # 安全配置：网络隔离、资源限制、用户权限
        docker_cmd = [
            "docker", "run", "--rm",           # 自动删除容器
            "--network", "none",               # 禁止网络访问
            "--memory", "256m",                 # 内存限制 256MB
            "--cpus", "1",                      # 单核 CPU
            "--user", "nobody",                 # 非 root 用户
            "--security-opt=no-new-privileges"  # 禁止提权
        ]

        # ========== 目录挂载配置 ==========
        # 根据参数动态挂载目录，确保访问控制

        if script_file:
            # 脚本文件方式：挂载 data/ 目录作为代码目录（只读）
            data_dir = os.path.join(script_dir, "data")
            if os.path.exists(data_dir):
                docker_cmd.append(f"-v {data_dir}:/app/code:ro")

        if input_path:
            # 输入文件：挂载 data/ 目录为只读输入目录
            data_dir = os.path.join(script_dir, "data")
            if os.path.exists(data_dir):
                docker_cmd.append(f"-v {data_dir}:/app/input:ro")

        if output_path:
            # 输出文件：挂载 output/ 目录为读写输出目录
            output_dir = os.path.join(script_dir, "output")
            os.makedirs(output_dir, exist_ok=True)  # 确保输出目录存在
            docker_cmd.append(f"-v {output_dir}:/app/output:rw")

        # ========== 执行方式选择 ==========
        if script_file:
            # ========== 模式1: 执行脚本文件 ==========
            script_safe_path = os.path.basename(script_file)  # 防止路径遍历
            docker_cmd.extend([
                "python:3.13-slim",           # 使用 Python 3.13 精简镜像
                "python", f"/app/code/{script_safe_path}"
            ])
            result = subprocess.run(
                docker_cmd,
                timeout=timeout,
                capture_output=True,             # 捕获标准输出和错误
                text=True                        # 文本模式
            )
        else:
            # ========== 模式2: 执行代码字符串 ==========
            docker_cmd.extend([
                "python:3.13-slim",
                "python", "-c", code_str         # -c 后直接跟代码字符串
            ])
            result = subprocess.run(
                docker_cmd,
                timeout=timeout,
                capture_output=True,
                text=True
            )

        # ========== 结果处理与返回 ==========
        if result.returncode == 0:
            # 执行成功
            output = result.stdout.strip()
            if output:
                return f"执行成功\n\n输出:\n{output}"
            else:
                return "执行成功，无输出"
        else:
            # 执行失败（非零退出码）
            error = result.stderr.strip()
            return f"执行失败（退出码 {result.returncode}）\n\n错误信息:\n{error}"

    # ========== 异常处理 ==========
    except subprocess.TimeoutExpired:
        return f"执行超时（超过 {timeout} 秒）"
    except FileNotFoundError:
        return "错误：未找到 Docker，请确保 Docker 已安装并运行"
    except Exception as e:
        return f"执行失败：{str(e)}"
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
    },
    {
        "type": "function",
        "function": {
            "name": "save_file",
            "description": "将内容保存到文件。支持保存分析结果、报告等文本内容。仅限 output/ 和 reports/ 目录。",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "文件路径，如 output/report.txt 或 reports/daily.md"
                    },
                    "content": {
                        "type": "string",
                        "description": "要保存的内容"
                    },
                    "encoding": {
                        "type": "string",
                        "description": "文件编码，默认 utf-8",
                        "default": "utf-8"
                    },
                    "mode": {
                        "type": "string",
                        "description": "写入模式：w=覆盖, a=追加",
                        "default": "w"
                    }
                },
                "required": ["file_path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_python",
            "description": "执行 Python 代码处理数据。支持两种方式：1) 直接传入代码字符串；2) 指定预写好的脚本文件。支持文件读写（需指定 input_path/output_path），禁止网络访问。",
            "parameters": {
                "type": "object",
                "properties": {
                    "code_str": {
                        "type": "string",
                        "description": "Python 代码字符串（与 script_file 二选一）。用于简单计算和处理。"
                    },
                    "script_file": {
                        "type": "string",
                        "description": "Python 脚本文件路径（与 code_str 二选一）。脚本存放在 data/ 目录，用于复杂处理。"
                    },
                    "input_path": {
                        "type": "string",
                        "description": "输入文件路径（data/目录），如 'data/input.txt'。代码中通过 /app/input/ 访问"
                    },
                    "output_path": {
                        "type": "string",
                        "description": "输出文件路径（output/目录），如 'output/result.txt'。代码中通过 /app/output/ 访问"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "执行超时时间（秒），默认 30",
                        "default": 30
                    }
                },
                "required": []
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

            elif function_name == "save_file":
                result = save_file(**arguments)

                # 调用工具后
                print(f"[DEBUG] 工具返回 - 长度: {len(result)}, 失败: {result.startswith('错误：')}")
                if result.startswith("错误：") or result.startswith("保存失败："):
                    print(f"[DEBUG] 保存失败详情: {result}")
                    return f"抱歉，保存遇到问题：{result}"
                else:
                    print(f"[DEBUG] {result}")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })

            elif function_name == "execute_python":
                result = execute_python(**arguments)

                # 调用工具后
                print(f"[DEBUG] 工具返回 - 长度: {len(result)}, 失败: {result.startswith('错误：') or result.startswith('执行失败')}")
                if result.startswith("错误：") or result.startswith("执行失败"):
                    print(f"[DEBUG] 执行失败详情: {result[:200]}...")
                    return f"抱歉，执行遇到问题：{result}"
                else:
                    result_preview = result[:300] if len(result) > 300 else result
                    print(f"[DEBUG] {result_preview}...")

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

def test_save_file():
    """测试 save_file 工具"""
    print("\n=== 测试 save_file 工具 ===")

    output_file = "reports/test_report.txt"
    # 测试 Agent 保存搜索结果
    result = run_agent(
        f"将'这是最新的agent报告'保存到 {output_file}"
    )
    print(f"\nAgent 回复:\n{result}")

    # 验证文件是否创建
    import os
    if os.path.exists(output_file):
        print("\n✓ 文件创建成功")
        with open(output_file, encoding='utf-8') as f:
            content = f.read()
            print(f"文件内容预览:\n{content[:300]}...")
    else:
        print(f"\n文件：{output_file}创建失败")

def test_execute_python():
    """测试 execute_python 工具"""
    print("\n=== 测试 execute_python 工具 ===")

    # 测试1: 直接调用函数（简单计算）
    print("\n--- 测试1: 简单计算 ---")
    result = execute_python(code_str="print('1+1=', 1+1); print('2*3=', 2*3)")
    print(f"结果:\n{result}")

    # 测试2: 复杂计算
    print("\n--- 测试2: 复杂计算 ---")
    code = """
import math
# 计算 1-100 的和
total = sum(range(1, 101))
print(f'1-100的和: {total}')

# 计算圆周率
print(f'圆周率: {math.pi:.6f}')

# 生成列表
squares = [x**2 for x in range(1, 6)]
print(f'平方数: {squares}')
"""
    result = execute_python(code_str=code)
    print(f"结果:\n{result}")

    # 测试3: 字符串处理
    print("\n--- 测试3: 字符串处理 ---")
    result = execute_python(code_str='text="Hello World"; print(text.upper()); print(text.split())')
    print(f"结果:\n{result}")

    # 测试4: 通过 Agent 调用
    print("\n--- 测试4: 通过 Agent 调用 ---")
    result = run_agent("用 Python 计算 1 到 100 的和，并计算 1 到 10 的平方数")
    print(f"Agent 回复:\n{result}")

def test_full_research_workflow():
    """测试完整调研工作流"""
    print("\n=== 完整调研任务测试 ===")
    print("任务：调研固态电池最新进展，生成分析报告")

    # 创建初始数据文件
    os.makedirs("data", exist_ok=True)
    with open("data/battery_info.txt", "w", encoding="utf-8") as f:
        f.write("固态电池技术背景：用固态电解质替代液态电解质，能量密度可提升至500Wh/kg以上。")

    # 完整调研任务
    result = run_agent(
        "请完成以下调研任务："
        "1. 搜索固态电池最新技术进展"
        "2. 读取 data/battery_info.txt 作为背景资料"
        "3. 用 Python 分析：假设能量密度从 300Wh/kg 提升到 500Wh/kg，计算提升百分比"
        "4. 将完整分析报告保存到 reports/solid_state_battery.md"
    )
    print(f"\n最终报告:\n{result}")

def run_tests():
    """运行所有测试"""
    #test_llm_connectivity()
    #test_web_search()
    #test_function_calling()
    #test_read_file()
    #test_save_file()
    #test_execute_python()
    test_full_research_workflow()

if __name__ == "__main__":
    run_tests()
