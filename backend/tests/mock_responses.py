"""
Mock 响应数据 - 按组件分类

每个 Mock 响应都是一个字符串：
- 结构化输出（with_structured_output）：合法 JSON 字符串，匹配对应 Pydantic schema
- 普通 LLM 调用：纯文本，包含相关关键词
"""

import json

# ============================================================
# 意图分类 Mock（JSON，匹配 IntentClassification schema）
# ============================================================

DIAGNOSIS_RESPONSE = json.dumps({
    "primary_intent": "diagnosis",
    "confidence": 0.92,
    "sub_type": "symptom_analysis",
    "sentiment": {"polarity": "neutral", "anxiety_score": 0.3, "urgency": "medium"},
    "entities": {"herbs": [], "prescriptions": [], "symptoms": ["失眠", "乏力", "食欲差"], "body_parts": [], "syndromes": [], "books": []},
    "reasoning": "用户描述了具体症状，属于诊断类意图",
    "suggested_follow_up": None,
    "requires_image": False,
    "route_source": "llm",
}, ensure_ascii=False)

PRESCRIPTION_RESPONSE = json.dumps({
    "primary_intent": "prescription",
    "confidence": 0.95,
    "sub_type": "query",
    "sentiment": {"polarity": "neutral", "anxiety_score": 0.0, "urgency": "low"},
    "entities": {"herbs": [], "prescriptions": ["六味地黄丸"], "symptoms": [], "body_parts": [], "syndromes": [], "books": []},
    "reasoning": "用户询问方剂信息",
    "suggested_follow_up": None,
    "requires_image": False,
    "route_source": "llm",
}, ensure_ascii=False)

HERB_RESPONSE = json.dumps({
    "primary_intent": "herb",
    "confidence": 0.93,
    "sub_type": "effect",
    "sentiment": {"polarity": "neutral", "anxiety_score": 0.0, "urgency": "low"},
    "entities": {"herbs": ["黄芪"], "prescriptions": [], "symptoms": [], "body_parts": [], "syndromes": [], "books": []},
    "reasoning": "用户询问药材功效",
    "suggested_follow_up": None,
    "requires_image": False,
    "route_source": "llm",
}, ensure_ascii=False)

WELLNESS_RESPONSE = json.dumps({
    "primary_intent": "wellness",
    "confidence": 0.88,
    "sub_type": "seasonal",
    "sentiment": {"polarity": "positive", "anxiety_score": 0.0, "urgency": "low"},
    "entities": {"herbs": [], "prescriptions": [], "symptoms": [], "body_parts": [], "syndromes": [], "books": []},
    "reasoning": "用户询问养生保健",
    "suggested_follow_up": None,
    "requires_image": False,
    "route_source": "llm",
}, ensure_ascii=False)

GENERAL_RESPONSE = json.dumps({
    "primary_intent": "general",
    "confidence": 0.7,
    "sub_type": None,
    "sentiment": {"polarity": "neutral", "anxiety_score": 0.0, "urgency": "low"},
    "entities": {"herbs": [], "prescriptions": [], "symptoms": [], "body_parts": [], "syndromes": [], "books": []},
    "reasoning": "用户询问基础知识",
    "suggested_follow_up": None,
    "requires_image": False,
    "route_source": "llm",
}, ensure_ascii=False)

# ============================================================
# collect_info Mock（JSON，匹配 ExtractedInfo schema）
# ============================================================

ROUND1_INFO = json.dumps({
    "chief_complaint": "失眠、乏力、食欲差",
    "onset_time": "最近两周",
    "duration": "两周",
    "cold_heat": "",
    "sweat": "",
    "head_body": "乏力",
    "urine_stool": "",
    "diet": "食欲差",
    "chest_abdomen": "",
    "sleep": "失眠",
    "emotion": "",
    "complexion": "",
    "other_symptoms": ["精神不振"],
}, ensure_ascii=False)

ROUND2_INFO = json.dumps({
    "chief_complaint": "",
    "onset_time": "",
    "duration": "",
    "cold_heat": "怕冷",
    "sweat": "无汗",
    "head_body": "",
    "urine_stool": "",
    "diet": "",
    "chest_abdomen": "",
    "sleep": "",
    "emotion": "",
    "complexion": "",
    "other_symptoms": [],
}, ensure_ascii=False)

# ============================================================
# follow_up Mock（JSON，匹配 FollowUpDecision schema）
# ============================================================

ASK_SYMPTOM = json.dumps({
    "action": "ask_symptom",
    "question": "请问您最近是否怕冷或者怕热？有没有出汗的情况？",
    "reasoning": "寒热和汗出信息缺失，需要追问",
    "missing_info": ["寒热", "汗出"],
}, ensure_ascii=False)

ASSESS_COMPLEXITY = json.dumps({
    "action": "assess_complexity",
    "question": "",
    "reasoning": "已收集足够的十问信息，进入辨证分析",
    "missing_info": [],
}, ensure_ascii=False)

# ============================================================
# 诊断 Mock（纯文本，包含关键词）
# ============================================================

SIMPLE_DIAGNOSIS_ANSWER = """### 一、四诊摘要
患者主诉失眠、乏力、食欲差两周。望诊：面色偏黄，舌淡苔白。闻诊：语声低微。问诊：失眠多梦，乏力倦怠，食欲不振，大便偏溏。切诊：脉细弱。

### 二、辨证分析
- 八纲辨证：里证、虚证、寒证
- 脏腑辨证：心脾两虚
- 辨证结论：心脾两虚证

### 三、调理建议
- 饮食调理：宜食健脾养心之品，如山药、莲子、大枣
- 起居调摄：规律作息，避免熬夜
- 情志调养：保持心情舒畅

### 四、注意事项
如症状持续加重，建议及时就医

### 五、温馨提示
以上分析仅供参考，不能替代专业医疗诊断。
"""

MODERATE_DIAGNOSIS_ANSWER = """### 一、四诊摘要
患者主诉失眠多梦、乏力倦怠、食欲不振。望诊：面色萎黄，舌淡胖有齿痕，苔白腻。闻诊：语声低怯。问诊：兼见畏寒肢冷、大便溏薄。切诊：脉沉细无力。

### 二、辨证分析
- 八纲辨证：里证、虚证、寒证
- 脏腑辨证：脾肾阳虚
- 辨证结论：脾肾阳虚证

### 三、参考资料
参照补中益气汤加减治疗类似病例。

### 四、调理建议
- 饮食调理：温补脾肾，宜食羊肉、核桃、山药
- 起居调摄：注意保暖，避免寒凉
- 情志调养：适当运动，舒缓情绪

### 五、注意事项
如出现严重畏寒、水肿等症状，建议及时就医

### 六、温馨提示
以上分析仅供参考，不能替代专业医疗诊断。
"""

# ============================================================
# 通用专家 Mock
# ============================================================

GENERAL_ANSWER = "中医是中国传统医学的重要组成部分，以阴阳五行学说为理论基础，通过望闻问切四诊合参进行辨证论治。中医强调天人合一的整体观念和辨证论治的个体化治疗原则。"

HERB_ANSWER = "黄芪，性甘、微温，归脾、肺经。功效：补气升阳、固表止汗、利水消肿、生津养血。主治气虚乏力、食少便溏、中气下陷、久泻脱肛、便血崩漏、表虚自汗等症状。"

PRESCRIPTION_ANSWER = "六味地黄丸出自宋代钱乙《小儿药证直诀》，由熟地黄、山萸肉、山药、泽泻、牡丹皮、茯苓六味药组成。功效滋阴补肾，主治肾阴亏损、头晕耳鸣、腰膝酸软、骨蒸潮热、盗汗遗精等症状。"

WELLNESS_ANSWER = "春季养生应注意养肝护阳。饮食方面宜多食绿色蔬菜和辛温发散之品，如韭菜、香菜、葱等。起居方面宜早睡早起，适当户外活动。情志方面应保持心情舒畅，避免抑郁恼怒。"
