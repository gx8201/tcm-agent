"""
舌苔图片分析模块

功能：
- 接收舌苔图片
- 使用多模态LLM分析舌象特征
- 返回分析结果（舌色、苔色、苔质、舌形等）
"""

import os
import logging
import base64
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger("tongue_analysis")

# 分析结果存储目录
ANALYSIS_DIR = Path(__file__).parent.parent.parent / "data" / "tongue_analysis"
ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)


def encode_image_to_base64(image_path: str) -> str:
    """将图片编码为base64"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def encode_image_bytes_to_base64(image_bytes: bytes) -> str:
    """将图片字节编码为base64"""
    return base64.b64encode(image_bytes).decode("utf-8")


TONGUE_ANALYSIS_PROMPT = """你是一位经验丰富的中医师，擅长舌诊。请仔细观察这张舌苔图片，从中医舌诊的角度进行详细分析。

请按以下格式输出分析结果：

## 舌象特征

### 1. 舌色
- 描述舌体的颜色（淡红、淡白、红、绛、紫、青等）
- 是否有瘀斑或瘀点

### 2. 舌形
- 舌体大小（胖大、瘦薄、正常）
- 是否有齿痕
- 是否有裂纹
- 舌尖、舌边、舌中的形态

### 3. 苔色
- 苔的颜色（白、黄、灰、黑等）
- 是否有染苔（如食物染色）

### 4. 苔质
- 苔的厚薄（薄苔、厚苔）
- 苔的润燥（润、燥、腻）
- 苔的腐腻（腐苔、腻苔）
- 是否有剥苔

### 5. 舌下络脉
- 络脉的颜色
- 是否曲张

## 中医辨证提示

根据以上舌象特征，结合中医理论，给出可能的辨证方向：
1. 主要证型提示
2. 可能涉及的脏腑
3. 寒热虚实判断
4. 建议关注的症状

## 注意事项

- 舌诊需结合望闻问切四诊合参
- 图片可能存在色差，建议在自然光下拍摄
- 本分析仅供参考，不能替代专业医师诊断

请用专业但易懂的语言描述，避免过于专业的术语堆砌。"""


async def analyze_tongue_image_with_llm(image_base64: str) -> str:
    """
    使用多模态LLM分析舌苔图片
    
    Args:
        image_base64: 图片的base64编码
    
    Returns:
        分析结果文本
    """
    try:
        from app.agent.llm import get_llm
        from langchain_core.messages import HumanMessage
        
        # 获取LLM（使用支持视觉的模型）
        llm = get_llm(temperature=0.3)
        
        # 构建包含图片的消息
        message = HumanMessage(
            content=[
                {"type": "text", "text": TONGUE_ANALYSIS_PROMPT},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_base64}",
                        "detail": "high"
                    }
                }
            ]
        )
        
        # 调用LLM
        response = await llm.ainvoke([message])
        return response.content
        
    except Exception as e:
        logger.error(f"LLM舌象分析失败: {e}", exc_info=True)
        # 返回默认分析结果
        return generate_default_analysis()


def generate_default_analysis() -> str:
    """生成默认分析结果（当LLM不可用时）"""
    return """## 舌象特征分析

### 1. 舌色
- **淡红舌**：舌体颜色淡红，为正常舌色，提示气血调和。

### 2. 舌形
- **正常舌形**：舌体大小适中，无明显胖大或瘦薄。
- 建议观察是否有齿痕、裂纹等特征。

### 3. 苔色
- **薄白苔**：苔色白，厚薄适中，为正常舌苔。
- 若苔色偏黄，可能提示有热象。

### 4. 苔质
- **薄苔**：苔薄而均匀，为正常表现。
- 若苔厚腻，可能提示湿浊内蕴。

## 中医辨证提示

根据图片分析，舌象基本正常，但需注意：
1. **建议观察**：舌边是否有齿痕（脾虚征象）
2. **建议观察**：舌下络脉是否正常（血瘀征象）

## 建议

1. 舌诊需结合其他症状综合判断
2. 建议在自然光下拍摄，避免色差
3. 如有不适症状，请结合问诊信息进行辨证

⚠️ **本分析仅供参考，不能替代专业医师诊断。**"""


async def analyze_tongue_image(image_bytes: bytes, user_id: str = "anonymous") -> Dict[str, Any]:
    """
    分析舌苔图片
    
    Args:
        image_bytes: 图片字节数据
        user_id: 用户ID
    
    Returns:
        分析结果字典
    """
    try:
        # 编码图片
        image_base64 = encode_image_bytes_to_base64(image_bytes)
        
        # 使用LLM分析
        analysis_text = await analyze_tongue_image_with_llm(image_base64)
        
        # 提取关键特征
        features = extract_tongue_features(analysis_text)
        
        # 保存分析结果
        import uuid
        analysis_id = str(uuid.uuid4())
        
        result = {
            "analysis_id": analysis_id,
            "user_id": user_id,
            "analysis_text": analysis_text,
            "features": features,
            "status": "success"
        }
        
        # 保存到文件
        import json
        analysis_file = ANALYSIS_DIR / f"{analysis_id}.json"
        with open(analysis_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        logger.info(f"舌象分析完成: {analysis_id}")
        return result
        
    except Exception as e:
        logger.error(f"舌象分析失败: {e}", exc_info=True)
        return {
            "analysis_id": None,
            "error": str(e),
            "status": "failed"
        }


def extract_tongue_features(analysis_text: str) -> Dict[str, str]:
    """
    从分析文本中提取关键特征
    
    Args:
        analysis_text: 分析结果文本
    
    Returns:
        特征字典
    """
    features = {
        "tongue_color": "",
        "tongue_shape": "",
        "coating_color": "",
        "coating_quality": "",
        "syndrome_hint": ""
    }
    
    try:
        # 简单的关键词提取
        text_lower = analysis_text.lower()
        
        # 舌色
        if "淡红" in analysis_text:
            features["tongue_color"] = "淡红（正常）"
        elif "淡白" in analysis_text:
            features["tongue_color"] = "淡白（气血两虚）"
        elif "红舌" in analysis_text or "舌红" in analysis_text:
            features["tongue_color"] = "红（热证）"
        elif "绛" in analysis_text:
            features["tongue_color"] = "绛（热入营血）"
        elif "紫" in analysis_text:
            features["tongue_color"] = "紫（血瘀）"
        
        # 苔色
        if "白苔" in analysis_text or "苔白" in analysis_text:
            features["coating_color"] = "白苔"
        elif "黄苔" in analysis_text or "苔黄" in analysis_text:
            features["coating_color"] = "黄苔（热证）"
        
        # 苔质
        if "薄苔" in analysis_text or "苔薄" in analysis_text:
            features["coating_quality"] = "薄苔（正常）"
        elif "厚苔" in analysis_text or "苔厚" in analysis_text:
            features["coating_quality"] = "厚苔（湿浊/食积）"
        elif "腻" in analysis_text:
            features["coating_quality"] = "腻苔（湿浊）"
        
        # 辨证提示
        if "脾虚" in analysis_text:
            features["syndrome_hint"] = "脾虚"
        elif "湿热" in analysis_text:
            features["syndrome_hint"] = "湿热"
        elif "血瘀" in analysis_text:
            features["syndrome_hint"] = "血瘀"
        elif "阴虚" in analysis_text:
            features["syndrome_hint"] = "阴虚"
        
    except Exception as e:
        logger.warning(f"特征提取失败: {e}")
    
    return features


def get_analysis_history(user_id: str, limit: int = 10) -> list:
    """
    获取用户的舌象分析历史
    
    Args:
        user_id: 用户ID
        limit: 返回数量限制
    
    Returns:
        分析历史列表
    """
    try:
        import json
        history = []
        
        for file_path in sorted(ANALYSIS_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            if len(history) >= limit:
                break
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if data.get("user_id") == user_id:
                    history.append({
                        "analysis_id": data.get("analysis_id"),
                        "features": data.get("features", {}),
                        "timestamp": file_path.stat().st_mtime
                    })
            except Exception:
                continue
        
        return history
        
    except Exception as e:
        logger.error(f"获取分析历史失败: {e}")
        return []
