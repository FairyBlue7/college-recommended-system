# -*- coding: utf-8 -*-
import sqlite3
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import os
from functools import wraps
from contextlib import contextmanager
import re
from analysis import (
    get_historical_data,
    calculate_trend,
    predict_rank,
    calculate_volatility,
    get_risk_level,
    get_volatility_level
)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'

# ========================
# 数据库路径
# ========================
DB_PATH = 'data/admissions.db'


# ========================
# 数据库连接工具（统一入口）
# ========================
def get_db_connection():
    """
    获取数据库连接，支持字典式访问
    注意: 调用者负责关闭连接
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # 允许使用列名访问数据
    return conn


@contextmanager
def get_db():
    """
    数据库连接上下文管理器（推荐使用）
    自动处理连接关闭，避免资源泄漏
    
    用法:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(...)
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# ========================
# 初始化数据库（创建所有表）
# ========================
def init_database():
    """初始化所有必需的数据库表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. 创建用户表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user'
    )
    ''')

    # 2. 创建录取数据表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS admissions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        province TEXT NOT NULL,
        exam_type TEXT NOT NULL,  -- "物理类" or "历史类"
        year INTEGER NOT NULL,
        school TEXT NOT NULL,
        major TEXT NOT NULL,
        min_score INTEGER,
        min_rank INTEGER
    )
    ''')

    # 3. 创建用户资料表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_profiles (
        user_id INTEGER PRIMARY KEY,
        province TEXT DEFAULT '广东',
        exam_type TEXT DEFAULT '物理类',
        last_rank INTEGER DEFAULT 10000,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    ''')

    # 4. 创建公告表（新增！）
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS announcements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        expire_time DATETIME,
        is_pinned BOOLEAN DEFAULT 0
    )
    ''')

    # 5. 创建志愿收藏表（新增！）
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_favorites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        school TEXT NOT NULL,
        major TEXT NOT NULL,
        category TEXT DEFAULT '稳',
        sort_order INTEGER DEFAULT 0,
        note TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        UNIQUE(user_id, school, major)
    )
    ''')

    # 6. 创建数据库索引
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_admissions_query 
        ON admissions(province, exam_type, year)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_admissions_school 
        ON admissions(school)
    ''')
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_favorites_user
        ON user_favorites(user_id)
    ''')

    # 7. 插入默认管理员
    try:
        admin_password = os.environ.get('ADMIN_PASSWORD', 'admin123')
        admin_hash = generate_password_hash(admin_password)
        cursor.execute('''
            INSERT INTO users (username, email, password_hash, role)
            VALUES (?, ?, ?, ?)
        ''', ('admin', 'admin@example.com', admin_hash, 'admin'))
    except sqlite3.IntegrityError:
        pass  # 已存在则跳过

    # 8. 插入示例录取数据
    cursor.execute("SELECT COUNT(*) FROM admissions")
    if cursor.fetchone()[0] == 0:
        sample_data = [
            ('广东', '物理类', 2023, '中山大学', '计算机科学与技术', 635, 4500),
            ('广东', '物理类', 2024, '华南理工大学', '人工智能', 628, 5200),
            ('广东', '历史类', 2023, '暨南大学', '新闻学', 605, 1800),
            ('广东', '物理类', 2023, '深圳大学', '电子信息工程', 615, 8500),
            ('广东', '历史类', 2024, '华南师范大学', '汉语言文学', 610, 2200)
        ]
        cursor.executemany('''
            INSERT INTO admissions 
            (province, exam_type, year, school, major, min_score, min_rank)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', sample_data)

    # 9. 插入测试公告
    cursor.execute("SELECT COUNT(*) FROM announcements")
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO announcements (title, content, is_pinned)
            VALUES 
            ('系统维护通知', '6月15日00:00-6:00进行系统升级，请提前保存志愿信息', 1),
            ('志愿填报指南更新', '新增2024年热门专业解读，<a href="/guide">点击查看</a>', 0)
        ''')

    conn.commit()
    conn.close()


# ========================
# 输入验证工具
# ========================
def validate_email(email: str) -> bool:
    """验证邮箱格式"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_username(username: str) -> bool:
    """验证用户名（3-20个字符，字母数字下划线）"""
    return 3 <= len(username) <= 20 and username.replace('_', '').isalnum()


# ========================
# 录取概率计算
# ========================
def calculate_admission_probability(student_rank: int, avg_rank: float) -> int:
    """简单的录取概率估算"""
    if avg_rank == 0:
        return 0
    ratio = student_rank / avg_rank
    if ratio < 0.85:
        return 95
    elif ratio < 0.95:
        return 70
    elif ratio < 1.05:
        return 50
    elif ratio < 1.15:
        return 30
    elif ratio < 1.3:
        return 15
    else:
        return 5


# ========================
# 获取录取数据
# ========================
def get_avg_rank_data(province: str, exam_type: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
    SELECT 
        school,
        major,
        AVG(min_rank) AS avg_rank,
        MIN(min_score) AS min_score
    FROM admissions
    WHERE province = ? 
      AND exam_type = ?
      AND year IN (2023, 2024, 2025)
      AND min_rank IS NOT NULL
    GROUP BY school, major
    HAVING COUNT(*) >= 1
    """
    cursor.execute(query, (province, exam_type))
    rows = cursor.fetchall()
    conn.close()

    result = []
    for row in rows:
        avg_rank = row[2]
        if avg_rank is not None:
            result.append({
                'school': row[0],
                'major': row[1],
                'avg_rank': round(avg_rank),
                'min_score': row[3] if row[3] else 0
            })
    return result


# ========================
# 登录装饰器
# ========================
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


# ========================
# 管理员权限装饰器
# ========================
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            flash('您没有管理员权限！', 'error')
            return redirect(url_for('recommend_page'))
        return f(*args, **kwargs)

    return decorated_function


# ========================
# 路由：首页 → 跳转推荐页或登录页
# ========================
@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('recommend_page'))
    return redirect(url_for('login'))


# ========================
# 注册页面
# ========================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip()
        password = request.form['password']

        if not username or not email or not password:
            flash('所有字段必填！', 'error')
            return render_template('register.html')

        if not validate_username(username):
            flash('用户名必须为3-20个字符，只能包含字母、数字和下划线！', 'error')
            return render_template('register.html')

        if not validate_email(email):
            flash('邮箱格式不正确！', 'error')
            return render_template('register.html')

        if len(password) < 6:
            flash('密码长度至少为6位！', 'error')
            return render_template('register.html')

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            password_hash = generate_password_hash(password)
            cursor.execute('''
                INSERT INTO users (username, email, password_hash, role)
                VALUES (?, ?, ?, 'user')
            ''', (username, email, password_hash))
            conn.commit()
            flash('注册成功，请登录！', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('用户名或邮箱已存在！', 'error')
        finally:
            conn.close()

    return render_template('register.html')


# ========================
# 登录页面
# ========================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, password_hash, role FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[2], password):
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['role'] = user[3]
            return redirect(url_for('recommend_page'))
        else:
            flash('用户名或密码错误！', 'error')

    return render_template('login.html')


# ========================
# 登出
# ========================
@app.route('/logout', methods=['GET', 'POST'])
def logout():
    session.clear()
    return redirect(url_for('login'))


# ========================
# 推荐页面（需登录）
# ========================
@app.route('/recommend-page')
@login_required
def recommend_page():
    user_id = session['user_id']

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT province, exam_type, last_rank 
        FROM user_profiles 
        WHERE user_id = ?
    ''', (user_id,))
    profile = cursor.fetchone()
    conn.close()

    defaults = {
        'province': profile[0] if profile else '广东',
        'exam_type': profile[1] if profile else '物理类',
        'rank': max(1, profile[2] if profile else 10000)
    }

    return render_template('index.html',
                           username=session.get('username'),
                           defaults=defaults)


# ========================
# 推荐 API（需登录）
# ========================
@app.route('/recommend', methods=['POST'])
@login_required
def recommend_api():
    try:
        student_rank = int(request.form['rank'])
        province = request.form['province']
        exam_type = request.form['exam_type']

        if student_rank <= 0:
            return jsonify({'error': '位次必须为正整数'}), 400

        all_records = get_avg_rank_data(province, exam_type)

        recommendations = {'冲': [], '稳': [], '保': []}

        lower_bound_rush = student_rank * 0.85
        upper_bound_rush = student_rank * 0.95
        lower_bound_safe = student_rank * 0.95
        upper_bound_safe = student_rank * 1.05
        lower_bound_conservative = student_rank * 1.1
        upper_bound_conservative = student_rank * 1.3

        for rec in all_records:
            avg_rank = rec['avg_rank']
            # 添加录取概率
            rec['probability'] = calculate_admission_probability(student_rank, avg_rank)

            if lower_bound_rush <= avg_rank < upper_bound_rush:
                recommendations['冲'].append(rec)
            elif lower_bound_safe <= avg_rank <= upper_bound_safe:
                recommendations['稳'].append(rec)
            elif lower_bound_conservative <= avg_rank <= upper_bound_conservative:
                recommendations['保'].append(rec)

        for key in recommendations:
            recommendations[key] = sorted(recommendations[key], key=lambda x: x['avg_rank'])

        return jsonify(recommendations)

    except (ValueError, KeyError):
        return jsonify({'error': '位次必须为有效的数字，且所有字段必填'}), 400
    except Exception as e:
        return jsonify({'error': f'服务器错误: {str(e)}'}), 500


# ========================
# 管理员后台页面
# ========================
@app.route('/admin')
@admin_required
def admin_dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, email, role FROM users ORDER BY id")
    users = cursor.fetchall()
    conn.close()
    return render_template('admin.html', users=users)


@app.route('/admin/delete/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    if user_id == session.get('user_id'):
        flash('不能删除自己！', 'error')
        return redirect(url_for('admin_dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT role FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        flash('用户不存在', 'error')
        conn.close()
        return redirect(url_for('admin_dashboard'))

    if user[0] == 'admin':
        flash('不能删除其他管理员！', 'error')
        conn.close()
        return redirect(url_for('admin_dashboard'))

    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    flash('用户删除成功！', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/toggle-admin/<int:user_id>/<action>', methods=['POST'])
@admin_required
def toggle_admin(user_id, action):
    if user_id == session.get('user_id'):
        flash('不能修改自己的角色！', 'error')
        return redirect(url_for('admin_dashboard'))

    if action not in ['promote', 'demote']:
        flash('无效操作！', 'error')
        return redirect(url_for('admin_dashboard'))

    conn = get_db_connection()
    cursor = conn.cursor()

    new_role = 'admin' if action == 'promote' else 'user'
    cursor.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, user_id))

    if cursor.rowcount == 0:
        flash('用户不存在！', 'error')
    else:
        flash(f'用户角色已{"提升为管理员" if action == "promote" else "降级为普通用户"}！', 'success')

    conn.commit()
    conn.close()
    return redirect(url_for('admin_dashboard'))


# ========================
# 个人资料路由
# ========================
@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == 'POST':
        province = request.form['province']
        exam_type = request.form['exam_type']
        rank = max(1, int(request.form['rank']))

        cursor.execute('''
            INSERT INTO user_profiles (user_id, province, exam_type, last_rank)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                province=excluded.province,
                exam_type=excluded.exam_type,
                last_rank=excluded.last_rank
        ''', (user_id, province, exam_type, rank))
        conn.commit()
        flash('个人资料已更新！', 'success')
        return redirect(url_for('recommend_page'))

    cursor.execute('''
        SELECT province, exam_type, last_rank 
        FROM user_profiles 
        WHERE user_id = ?
    ''', (user_id,))
    profile = cursor.fetchone()

    if not profile:
        profile = ('广东', '物理类', 10000)
        cursor.execute('''
            INSERT OR IGNORE INTO user_profiles (user_id, province, exam_type, last_rank)
            VALUES (?, ?, ?, ?)
        ''', (user_id, *profile))
        conn.commit()

    conn.close()

    return render_template('profile.html',
                           province=profile[0],
                           exam_type=profile[1],
                           last_rank=profile[2])


# ========================
# 公告系统路由（新增！）
# ========================

@app.route('/announcements')
@login_required
def announcements_page():
    """公告列表页面"""
    conn = get_db_connection()
    announcements = conn.execute('''
        SELECT * FROM announcements 
        WHERE (expire_time IS NULL OR expire_time > datetime('now'))
        ORDER BY is_pinned DESC, create_time DESC
    ''').fetchall()
    conn.close()

    return render_template('announcements.html',
                           announcements=announcements,
                           username=session.get('username'))


@app.route('/api/announcements/latest')
@login_required
def latest_announcements():
    """返回首页需要的3条最新公告（JSON格式）"""
    conn = get_db_connection()
    anns = conn.execute('''
        SELECT id, title, 
               SUBSTR(REPLACE(REPLACE(content, '<br>', ' '), '</p>', ' '), 0, 45) as summary,
               is_pinned
        FROM announcements
        WHERE (expire_time IS NULL OR expire_time > datetime('now'))
        ORDER BY is_pinned DESC, create_time DESC
        LIMIT 3
    ''').fetchall()
    conn.close()

    return jsonify([dict(ann) for ann in anns])


@app.route('/admin/announcements', methods=['GET', 'POST'])
@admin_required
def manage_announcements():
    conn = get_db_connection()

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        expire = request.form.get('expire_time') or None
        is_pinned = 1 if request.form.get('is_pinned') else 0

        conn.execute('''
            INSERT INTO announcements (title, content, expire_time, is_pinned)
            VALUES (?, ?, ?, ?)
        ''', (title, content, expire, is_pinned))
        conn.commit()
        flash('公告发布成功！', 'success')

    announcements = conn.execute('''
        SELECT * FROM announcements 
        ORDER BY is_pinned DESC, create_time DESC
    ''').fetchall()

    conn.close()
    return render_template('admin_announcements.html',
                           announcements=announcements,
                           username=session.get('username'))


@app.route('/admin/delete-announcement/<int:ann_id>', methods=['POST'])
@admin_required
def delete_announcement(ann_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM announcements WHERE id = ?', (ann_id,))
    conn.commit()
    conn.close()
    flash('公告删除成功！', 'success')
    return redirect(url_for('manage_announcements'))


# ========================
# 位次分析路由（新增！）
# ========================

@app.route('/analysis-page')
@login_required
def analysis_page():
    """位次分析页面"""
    return render_template('analysis.html', username=session.get('username'))


@app.route('/api/analysis/<school>/<major>')
@login_required
def get_school_analysis(school, major):
    """
    获取学校专业的位次分析数据
    
    URL参数:
        - province: 省份
        - exam_type: 考试类型
        - student_rank: 学生位次（可选）
    """
    try:
        # 获取查询参数
        province = request.args.get('province', '广东')
        exam_type = request.args.get('exam_type', '物理类')
        student_rank = request.args.get('student_rank', type=int)
        
        # 获取历史数据
        historical_data = get_historical_data(school, major, province, exam_type)
        
        if not historical_data:
            return jsonify({
                'error': '未找到该学校专业的历史数据',
                'school': school,
                'major': major
            }), 404
        
        # 提取位次
        ranks = [d['min_rank'] for d in historical_data]
        
        # 计算趋势
        trend, trend_description = calculate_trend(historical_data)
        
        # 预测位次
        prediction = predict_rank(ranks)
        
        # 计算波动
        volatility_value = calculate_volatility(ranks)
        volatility = get_volatility_level(volatility_value)
        
        # 评估风险（如果提供了学生位次）
        risk_assessment = None
        if student_rank:
            risk_assessment = get_risk_level(
                student_rank,
                prediction['predicted_rank'],
                volatility_value
            )
        
        return jsonify({
            'school': school,
            'major': major,
            'historical_data': historical_data,
            'trend': trend,
            'trend_description': trend_description,
            'predicted_rank': prediction['predicted_rank'],
            'predicted_range': {
                'min': prediction['min'],
                'max': prediction['max']
            },
            'volatility': volatility,
            'volatility_value': int(volatility_value),
            'risk_assessment': risk_assessment
        })
        
    except Exception as e:
        return jsonify({'error': f'分析失败: {str(e)}'}), 500


# ========================
# 志愿表管理路由（新增！）
# ========================

@app.route('/wishlist')
@login_required
def wishlist_page():
    """志愿表管理页面"""
    return render_template('wishlist.html', username=session.get('username'))


@app.route('/api/favorites', methods=['GET', 'POST', 'DELETE'])
@login_required
def manage_favorites():
    """管理志愿收藏"""
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'GET':
        # 获取用户的所有收藏
        cursor.execute('''
            SELECT id, school, major, category, sort_order, note, created_at
            FROM user_favorites
            WHERE user_id = ?
            ORDER BY sort_order ASC, created_at DESC
        ''', (user_id,))
        favorites = cursor.fetchall()
        conn.close()
        
        result = []
        for fav in favorites:
            result.append({
                'id': fav['id'],
                'school': fav['school'],
                'major': fav['major'],
                'category': fav['category'],
                'sort_order': fav['sort_order'],
                'note': fav['note'],
                'created_at': fav['created_at']
            })
        
        return jsonify(result)
    
    elif request.method == 'POST':
        # 添加收藏
        data = request.get_json()
        school = data.get('school', '').strip()
        major = data.get('major', '').strip()
        category = data.get('category', '稳')
        note = data.get('note', '')
        
        if not school or not major:
            return jsonify({'error': '学校和专业不能为空'}), 400
        
        if category not in ['冲', '稳', '保']:
            category = '稳'
        
        try:
            # 获取当前最大排序号
            cursor.execute('''
                SELECT COALESCE(MAX(sort_order), 0) + 1 as next_order
                FROM user_favorites
                WHERE user_id = ?
            ''', (user_id,))
            next_order = cursor.fetchone()['next_order']
            
            cursor.execute('''
                INSERT INTO user_favorites (user_id, school, major, category, sort_order, note)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, school, major, category, next_order, note))
            conn.commit()
            
            # 返回新创建的收藏
            fav_id = cursor.lastrowid
            conn.close()
            
            return jsonify({
                'success': True,
                'message': '添加成功',
                'id': fav_id
            })
        except sqlite3.IntegrityError:
            conn.close()
            return jsonify({'error': '该志愿已存在'}), 400
    
    elif request.method == 'DELETE':
        # 删除收藏
        data = request.get_json()
        fav_id = data.get('id')
        
        if not fav_id:
            return jsonify({'error': 'ID不能为空'}), 400
        
        cursor.execute('''
            DELETE FROM user_favorites
            WHERE id = ? AND user_id = ?
        ''', (fav_id, user_id))
        
        if cursor.rowcount == 0:
            conn.close()
            return jsonify({'error': '志愿不存在或无权删除'}), 404
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': '删除成功'})


@app.route('/api/favorites/reorder', methods=['POST'])
@login_required
def reorder_favorites():
    """调整志愿顺序"""
    user_id = session['user_id']
    data = request.get_json()
    ordered_ids = data.get('ordered_ids', [])
    
    if not ordered_ids:
        return jsonify({'error': '顺序列表不能为空'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 更新排序
        for index, fav_id in enumerate(ordered_ids):
            cursor.execute('''
                UPDATE user_favorites
                SET sort_order = ?
                WHERE id = ? AND user_id = ?
            ''', (index, fav_id, user_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': '排序更新成功'})
    except Exception as e:
        conn.close()
        return jsonify({'error': f'排序失败: {str(e)}'}), 500


@app.route('/api/favorites/<int:fav_id>', methods=['PUT'])
@login_required
def update_favorite(fav_id):
    """更新志愿（修改分类或备注）"""
    user_id = session['user_id']
    data = request.get_json()
    
    category = data.get('category')
    note = data.get('note')
    
    if not category and note is None:
        return jsonify({'error': '至少需要提供一个更新字段'}), 400
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Use predefined update statements for security
    # This prevents SQL injection by avoiding dynamic query construction
    # Each possible update scenario uses a fixed SQL statement with parameters
    if category and note is not None:
        # Update both fields
        if category not in ['冲', '稳', '保']:
            conn.close()
            return jsonify({'error': '无效的分类'}), 400
        cursor.execute('''
            UPDATE user_favorites
            SET category = ?, note = ?
            WHERE id = ? AND user_id = ?
        ''', (category, note, fav_id, user_id))
    elif category:
        # Update only category
        if category not in ['冲', '稳', '保']:
            conn.close()
            return jsonify({'error': '无效的分类'}), 400
        cursor.execute('''
            UPDATE user_favorites
            SET category = ?
            WHERE id = ? AND user_id = ?
        ''', (category, fav_id, user_id))
    elif note is not None:
        # Update only note
        cursor.execute('''
            UPDATE user_favorites
            SET note = ?
            WHERE id = ? AND user_id = ?
        ''', (note, fav_id, user_id))
    
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({'error': '志愿不存在或无权修改'}), 404
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': '更新成功'})


# ========================
# 启动应用
# ========================
if __name__ == '__main__':
    # 确保 data 目录存在
    os.makedirs('data', exist_ok=True)

    # 初始化完整数据库
    init_database()

    print("\n" + "=" * 50)
    print("✅ 系统启动成功！")
    print("👤 管理员账号: admin / admin123")
    print("🌐 访问地址: http://localhost:5000")
    print("-" * 50)
    print("💡 首次使用建议:")
    print("1. 用管理员账号登录 /admin")
    print("2. 添加真实录取数据到 admissions 表")
    print("3. 普通用户注册后需在 /profile 完善资料")
    print("=" * 50 + "\n")

    app.run(debug=True, host='0.0.0.0', port=5000)