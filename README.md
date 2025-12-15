# 高考志愿推荐系统

一个基于 Flask 的高考志愿智能推荐系统，帮助考生根据位次、省份和考试类型获取科学的院校专业推荐。

## 功能特性

### 核心功能
- **智能推荐算法**：基于历史录取数据，按"冲、稳、保"三档推荐院校专业
- **录取概率估算**：为每个推荐结果提供录取概率参考
- **用户系统**：支持用户注册、登录和个人资料管理
- **公告系统**：管理员可发布系统公告，支持置顶和过期管理
- **管理后台**：完善的用户管理和权限控制

### 技术特性
- 安全的会话管理和密码加密
- CSRF 防护（敏感操作使用 POST 请求）
- 数据库查询优化（索引支持）
- 环境变量配置管理

## 技术栈

- **后端框架**：Flask 2.3+
- **数据库**：SQLite3
- **安全**：Werkzeug (密码哈希)
- **前端**：HTML5 + CSS3 + JavaScript + Bootstrap

## 安装步骤

### 1. 克隆项目
```bash
git clone https://github.com/FairyBlue7/college-recommended-system.git
cd college-recommended-system
```

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 配置环境变量（可选）
```bash
# 复制环境变量模板
cp college-recommender/.env.example college-recommender/.env

# 编辑 .env 文件，设置安全的密钥
SECRET_KEY=your-random-secret-key-here
ADMIN_PASSWORD=your-secure-admin-password
```

**重要提示**：
- 生产环境必须设置 `SECRET_KEY` 环境变量
- 建议修改默认管理员密码 `ADMIN_PASSWORD`

### 4. 运行应用
```bash
cd college-recommender
python app.py
```

应用将在 `http://localhost:5000` 启动

## 配置说明

### 环境变量

| 变量名 | 说明 | 默认值 | 是否必需 |
|--------|------|--------|----------|
| `SECRET_KEY` | Flask 会话密钥 | `dev-secret-key-change-in-production` | 生产环境必需 |
| `ADMIN_PASSWORD` | 默认管理员密码 | `admin123` | 推荐修改 |
| `DB_PATH` | 数据库文件路径 | `data/admissions.db` | 否 |

### 数据库初始化

首次运行时，系统会自动：
1. 创建 `data` 目录
2. 初始化数据库表结构
3. 创建默认管理员账号（`admin` / `admin123`）
4. 插入示例录取数据

## 使用方法

### 普通用户
1. **注册账号**：访问 `/register` 创建账号
2. **完善资料**：登录后访问 `/profile` 填写省份、考试类型和位次
3. **获取推荐**：在首页输入位次，点击"开始推荐"

### 管理员
1. **用户管理**：访问 `/admin` 管理用户、分配管理员权限
2. **公告管理**：访问 `/admin/announcements` 发布系统公告

## API 接口说明

### 推荐接口
```http
POST /recommend
Content-Type: application/x-www-form-urlencoded

rank=10000&province=广东&exam_type=物理类
```

**响应示例**：
```json
{
  "冲": [
    {
      "school": "中山大学",
      "major": "计算机科学与技术",
      "avg_rank": 4500,
      "min_score": 635,
      "probability": 70
    }
  ],
  "稳": [...],
  "保": [...]
}
```

### 公告接口
```http
GET /api/announcements/latest
```

**响应示例**：
```json
[
  {
    "id": 1,
    "title": "系统维护通知",
    "summary": "6月15日00:00-6:00进行系统升级...",
    "is_pinned": 1
  }
]
```

## 项目结构

```
college-recommended-system/
├── README.md                    # 项目文档
├── requirements.txt             # Python 依赖
├── .gitignore                   # Git 忽略规则
└── college-recommender/
    ├── .env.example             # 环境变量模板
    ├── app.py                   # 主应用程序
    ├── data/
    │   └── admissions.db        # SQLite 数据库
    ├── static/                  # 静态资源
    └── templates/               # HTML 模板
        ├── index.html           # 推荐页面
        ├── login.html           # 登录页面
        ├── register.html        # 注册页面
        ├── profile.html         # 个人资料
        ├── admin.html           # 用户管理
        ├── admin_announcements.html  # 公告管理
        └── announcements.html   # 公告列表
```

## 安全建议

1. **生产环境部署**：
   - 设置强随机的 `SECRET_KEY`
   - 修改默认管理员密码
   - 使用 HTTPS 协议
   - 禁用 Flask 的 debug 模式

2. **数据备份**：
   - 定期备份 `data/admissions.db` 数据库文件

3. **权限控制**：
   - 敏感操作已使用 POST 请求防护 CSRF
   - 管理员功能需要 `@admin_required` 装饰器保护

## 开发计划

- [ ] 添加更多省份和年份的录取数据
- [ ] 支持批量导入历史录取数据
- [ ] 优化推荐算法（考虑专业热度、就业率等因素）
- [ ] 添加数据可视化图表
- [ ] 支持志愿表导出功能

## 许可证

MIT License

## 贡献者

欢迎提交 Issue 和 Pull Request！

## 联系方式

如有问题，请提交 [GitHub Issue](https://github.com/FairyBlue7/college-recommended-system/issues)
