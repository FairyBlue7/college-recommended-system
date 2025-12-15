# -*- coding: utf-8 -*-
"""
位次分析模块
提供历史数据分析、趋势预测、波动计算和风险评估功能
"""

import sqlite3
from typing import List, Dict, Optional, Tuple
import statistics


def get_db_connection():
    """获取数据库连接"""
    conn = sqlite3.connect('data/admissions.db')
    conn.row_factory = sqlite3.Row
    return conn


def get_historical_data(school: str, major: str, province: str, exam_type: str) -> List[Dict]:
    """
    获取某学校专业的历年录取数据
    
    Args:
        school: 学校名称
        major: 专业名称
        province: 省份
        exam_type: 考试类型（物理类/历史类）
    
    Returns:
        历年数据列表，按年份升序排列
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = """
        SELECT year, min_score, min_rank
        FROM admissions
        WHERE school = ? AND major = ? AND province = ? AND exam_type = ?
        AND min_rank IS NOT NULL
        ORDER BY year ASC
    """
    
    cursor.execute(query, (school, major, province, exam_type))
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for row in rows:
        result.append({
            'year': row['year'],
            'min_score': row['min_score'],
            'min_rank': row['min_rank']
        })
    
    return result


def calculate_trend(data_list: List[Dict]) -> Tuple[str, str]:
    """
    计算位次变化趋势
    
    Args:
        data_list: 历年数据列表，包含 year 和 min_rank
    
    Returns:
        (趋势, 趋势描述) 元组
        趋势: "上升" / "下降" / "稳定"
    """
    if len(data_list) < 2:
        return "稳定", "数据不足，无法判断趋势"
    
    # 提取位次数据
    ranks = [d['min_rank'] for d in data_list]
    
    # 计算简单线性趋势（位次变小=竞争加剧=上升趋势）
    n = len(ranks)
    x_values = list(range(n))
    x_mean = sum(x_values) / n
    y_mean = sum(ranks) / n
    
    # 计算斜率
    numerator = sum((x_values[i] - x_mean) * (ranks[i] - y_mean) for i in range(n))
    denominator = sum((x_values[i] - x_mean) ** 2 for i in range(n))
    
    if denominator == 0:
        return "稳定", "位次保持稳定"
    
    slope = numerator / denominator
    
    # 判断趋势（位次变小=slope<0，表示竞争加剧）
    if slope < -100:  # 每年下降超过100位
        return "上升", f"近{n}年位次持续上升，竞争加剧"
    elif slope > 100:  # 每年上升超过100位
        return "下降", f"近{n}年位次持续下降，竞争降低"
    else:
        return "稳定", f"近{n}年位次相对稳定，波动不大"


def predict_rank(historical_ranks: List[int]) -> Dict:
    """
    基于历史数据预测今年位次范围
    
    Args:
        historical_ranks: 历史位次列表（按时间顺序）
    
    Returns:
        包含预测位次和置信区间的字典
    """
    if len(historical_ranks) < 2:
        return {
            'predicted_rank': historical_ranks[0] if historical_ranks else 0,
            'min': historical_ranks[0] if historical_ranks else 0,
            'max': historical_ranks[0] if historical_ranks else 0
        }
    
    # 简单线性回归预测
    n = len(historical_ranks)
    x_values = list(range(n))
    x_mean = sum(x_values) / n
    y_mean = sum(historical_ranks) / n
    
    # 计算斜率和截距
    numerator = sum((x_values[i] - x_mean) * (historical_ranks[i] - y_mean) for i in range(n))
    denominator = sum((x_values[i] - x_mean) ** 2 for i in range(n))
    
    if denominator == 0:
        # 无法预测，返回平均值
        avg_rank = int(y_mean)
        std_dev = calculate_volatility(historical_ranks)
        return {
            'predicted_rank': avg_rank,
            'min': max(1, int(avg_rank - 1.5 * std_dev)),
            'max': int(avg_rank + 1.5 * std_dev)
        }
    
    slope = numerator / denominator
    intercept = y_mean - slope * x_mean
    
    # 预测下一年
    next_x = n  # 下一个时间点
    predicted = slope * next_x + intercept
    
    # 计算置信区间（±1.5倍标准差）
    std_dev = calculate_volatility(historical_ranks)
    confidence_interval = 1.5 * std_dev
    
    return {
        'predicted_rank': max(1, int(predicted)),
        'min': max(1, int(predicted - confidence_interval)),
        'max': int(predicted + confidence_interval)
    }


def calculate_volatility(ranks: List[int]) -> float:
    """
    计算位次波动程度（标准差）
    
    Args:
        ranks: 位次列表
    
    Returns:
        标准差值
    """
    if len(ranks) < 2:
        return 0.0
    
    return statistics.stdev(ranks)


def get_risk_level(student_rank: int, predicted_rank: int, volatility: float) -> str:
    """
    评估录取风险等级
    
    Args:
        student_rank: 学生位次
        predicted_rank: 预测位次
        volatility: 波动程度（标准差）
    
    Returns:
        风险等级：低风险 / 中风险 / 高风险
    """
    # 计算预测范围
    predicted_min = predicted_rank - 1.5 * volatility
    predicted_max = predicted_rank + 1.5 * volatility
    
    if student_rank < predicted_min:
        return "低风险"
    elif student_rank <= predicted_max:
        return "中风险"
    else:
        return "高风险"


def get_volatility_level(volatility: float) -> str:
    """
    将波动数值转换为等级描述
    
    Args:
        volatility: 波动标准差
    
    Returns:
        波动等级：低 / 中 / 高
    """
    if volatility < 300:
        return "低"
    elif volatility < 800:
        return "中"
    else:
        return "高"
