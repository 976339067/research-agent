import os
from openai import OpenAI

from dotenv import load_dotenv

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

response = client.chat.completions.create(
    model="GLM-4.7-Flash",
    messages=[{"role": "user", "content": "你好，请用一句话介绍你自己"}]
)

print(response.choices[0].message.content)
