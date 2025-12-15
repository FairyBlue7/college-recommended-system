# -*- coding: utf-8 -*-
"""
数据导入脚本
用于从 CSV 文件批量导入高考录取数据到数据库
"""
import csv
import sqlite3
import sys
import os
from typing import List, Dict, Tuple


DB_PATH = 'data/admissions.db'


def detect_encoding(file_path: str) -> str:
    """
    自动检测 CSV 文件编码（UTF-8 或 GBK）
    """
    encodings = ['utf-8', 'gbk', 'utf-8-sig']
    
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                f.read()
            return encoding
        except (UnicodeDecodeError, UnicodeError):
            continue
    
    # 默认返回 utf-8
    return 'utf-8'


def validate_row(row: Dict[str, str], line_num: int) -> Tuple[bool, str]:
    """
    验证单行数据的有效性
    返回 (是否有效, 错误信息)
    """
    required_fields = ['province', 'exam_type', 'year', 'school', 'major', 'min_score', 'min_rank']
    
    # 检查必填字段
    for field in required_fields:
        if field not in row or not row[field] or str(row[field]).strip() == '':
            return False, f"第 {line_num} 行缺少必填字段: {field}"
    
    # 验证年份
    try:
        year = int(row['year'])
        if year < 2000 or year > 2030:
            return False, f"第 {line_num} 行年份不合理: {year}"
    except ValueError:
        return False, f"第 {line_num} 行年份格式错误: {row['year']}"
    
    # 验证分数
    try:
        score = float(row['min_score'])
        if score < 0 or score > 750:
            return False, f"第 {line_num} 行分数不合理: {score}"
    except ValueError:
        return False, f"第 {line_num} 行分数格式错误: {row['min_score']}"
    
    # 验证位次
    try:
        rank = int(float(row['min_rank']))  # 先转 float 再转 int，处理 "3500.0" 这样的情况
        if rank < 0:
            return False, f"第 {line_num} 行位次不能为负数: {rank}"
    except ValueError:
        return False, f"第 {line_num} 行位次格式错误: {row['min_rank']}"
    
    return True, ""


def read_csv_file(file_path: str) -> Tuple[List[Dict], List[str]]:
    """
    读取 CSV 文件并返回数据行和错误信息
    返回 (数据行列表, 错误信息列表)
    """
    if not os.path.exists(file_path):
        return [], [f"文件不存在: {file_path}"]
    
    encoding = detect_encoding(file_path)
    print(f"检测到文件编码: {encoding}")
    
    data_rows = []
    errors = []
    
    try:
        with open(file_path, 'r', encoding=encoding) as f:
            # 移除 BOM 标记（如果存在）
            content = f.read()
            if content.startswith('\ufeff'):
                content = content[1:]
            
            # 使用 StringIO 来处理清理后的内容
            from io import StringIO
            reader = csv.DictReader(StringIO(content))
            
            for i, row in enumerate(reader, start=2):  # 从第2行开始（第1行是标题）
                # 清理字段名和值中的空白字符
                row = {k.strip(): v.strip() if v else '' for k, v in row.items()}
                
                # 验证数据
                is_valid, error_msg = validate_row(row, i)
                if not is_valid:
                    errors.append(error_msg)
                    continue
                
                data_rows.append(row)
    
    except Exception as e:
        errors.append(f"读取文件时发生错误: {str(e)}")
    
    return data_rows, errors


def import_to_database(data_rows: List[Dict], db_path: str = DB_PATH) -> Dict[str, int]:
    """
    批量导入数据到数据库
    返回统计信息: {'success': 成功数, 'skipped': 跳过数, 'failed': 失败数}
    """
    stats = {'success': 0, 'skipped': 0, 'failed': 0}
    
    if not os.path.exists(db_path):
        print(f"错误: 数据库文件不存在 {db_path}")
        return stats
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        for row in data_rows:
            try:
                province = row['province'].strip()
                exam_type = row['exam_type'].strip()
                year = int(row['year'])
                school = row['school'].strip()
                major = row['major'].strip()
                min_score = int(float(row['min_score']))
                min_rank = int(float(row['min_rank']))
                
                # 检查是否已存在相同记录
                cursor.execute('''
                    SELECT id FROM admissions 
                    WHERE province = ? AND exam_type = ? AND year = ? 
                    AND school = ? AND major = ?
                ''', (province, exam_type, year, school, major))
                
                existing = cursor.fetchone()
                
                if existing:
                    stats['skipped'] += 1
                else:
                    cursor.execute('''
                        INSERT INTO admissions 
                        (province, exam_type, year, school, major, min_score, min_rank)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (province, exam_type, year, school, major, min_score, min_rank))
                    stats['success'] += 1
            
            except Exception as e:
                stats['failed'] += 1
                print(f"导入失败: {school} - {major}: {str(e)}")
        
        conn.commit()
    
    except Exception as e:
        conn.rollback()
        print(f"数据库操作失败: {str(e)}")
    
    finally:
        conn.close()
    
    return stats


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python import_data.py <csv_file_path>")
        print("示例: python import_data.py data/sample_data.csv")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    
    print("=" * 60)
    print("高考录取数据导入工具")
    print("=" * 60)
    print(f"CSV 文件: {csv_file}")
    print()
    
    # 读取 CSV 文件
    print("正在读取 CSV 文件...")
    data_rows, errors = read_csv_file(csv_file)
    
    if errors:
        print(f"\n⚠️  发现 {len(errors)} 个错误:")
        for error in errors[:10]:  # 只显示前10个错误
            print(f"  - {error}")
        if len(errors) > 10:
            print(f"  ... 还有 {len(errors) - 10} 个错误")
        print()
    
    if not data_rows:
        print("❌ 没有有效的数据可以导入")
        sys.exit(1)
    
    print(f"✅ 读取成功，共 {len(data_rows)} 条有效数据")
    print()
    
    # 导入到数据库
    print("正在导入数据库...")
    stats = import_to_database(data_rows)
    
    # 显示统计结果
    print()
    print("=" * 60)
    print("导入完成！")
    print("=" * 60)
    print(f"✅ 成功导入: {stats['success']} 条")
    print(f"⏭️  跳过重复: {stats['skipped']} 条")
    print(f"❌ 导入失败: {stats['failed']} 条")
    print(f"📊 总计处理: {stats['success'] + stats['skipped'] + stats['failed']} 条")
    print("=" * 60)


if __name__ == '__main__':
    main()
