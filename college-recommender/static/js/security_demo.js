/**
 * SQL 注入安全演示 - 交互功能
 * 实时显示 SQL 查询构建、Payload 快捷填充、攻击结果动画
 */

// 实时更新 SQL 查询预览
function updateSQLPreview(usernameValue, passwordValue) {
    const sqlOutput = document.getElementById('sqlOutput');
    if (!sqlOutput) return;
    
    // 构建 SQL 查询
    const query = `SELECT * FROM users WHERE username = '${usernameValue}' AND password_hash = '${passwordValue}'`;
    sqlOutput.textContent = query;
    
    // 检测是否包含注入特征
    const dangerousPatterns = [
        "'", '"', '--', '/*', '*/',
        'UNION', 'SELECT', 'DROP', 'DELETE', 'INSERT', 'UPDATE',
        'OR', 'AND', '1=1', '1 =1'
    ];
    
    const upperQuery = query.toUpperCase();
    const isDangerous = dangerousPatterns.some(pattern => 
        upperQuery.includes(pattern.toUpperCase())
    );
    
    // 应用危险样式
    if (isDangerous) {
        sqlOutput.classList.add('dangerous');
        highlightSQLKeywords(sqlOutput);
    } else {
        sqlOutput.classList.remove('dangerous');
    }
}

// 高亮 SQL 关键词
// 注意：此函数仅用于显示目的，所有内容都经过 escapeHTML 转义后才插入 DOM
// 输入来源：用户在输入框中的内容 -> 通过 textContent 提取 -> escapeHTML 转义 -> 添加样式 -> innerHTML
// 安全保证：所有用户输入都经过 escapeHTML() 函数转义，防止 XSS
function highlightSQLKeywords(element) {
    const text = element.textContent;
    
    // SQL 关键词列表
    const keywords = ['SELECT', 'FROM', 'WHERE', 'AND', 'OR', 'UNION', 'DROP', 'INSERT', 'UPDATE', 'DELETE'];
    
    // 创建安全的高亮版本
    let highlightedHTML = '';
    let currentPos = 0;
    const textUpper = text.toUpperCase();
    
    // 查找所有关键词位置
    const matches = [];
    keywords.forEach(keyword => {
        const regex = new RegExp(`\\b${keyword}\\b`, 'gi');
        let match;
        while ((match = regex.exec(text)) !== null) {
            matches.push({ start: match.index, end: match.index + keyword.length, text: match[0] });
        }
    });
    
    // 按位置排序
    matches.sort((a, b) => a.start - b.start);
    
    // 构建高亮HTML（安全方式 - 所有内容都经过 escapeHTML 转义）
    matches.forEach(match => {
        if (match.start >= currentPos) {
            // 添加关键词之前的普通文本（已转义）
            highlightedHTML += escapeHTML(text.substring(currentPos, match.start));
            // 添加高亮的关键词（已转义）
            highlightedHTML += `<span style="color: #ff79c6; font-weight: bold;">${escapeHTML(match.text)}</span>`;
            currentPos = match.end;
        }
    });
    
    // 添加剩余文本（已转义）
    highlightedHTML += escapeHTML(text.substring(currentPos));
    
    // 安全：所有内容都已转义，可以安全使用 innerHTML
    element.innerHTML = highlightedHTML;
}

// HTML 转义函数（防止 XSS）
function escapeHTML(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// 显示反馈消息
function showFeedback(message, type = 'success') {
    const feedbackContainer = document.getElementById('feedbackContainer');
    if (!feedbackContainer) return;
    
    const feedbackDiv = document.createElement('div');
    feedbackDiv.className = `feedback-${type}`;
    
    // 使用 textContent 防止 XSS
    const icon = document.createElement('i');
    icon.className = `fas fa-${type === 'success' ? 'check-circle' : 'exclamation-circle'}`;
    feedbackDiv.appendChild(icon);
    
    const messageText = document.createTextNode(' ' + message);
    feedbackDiv.appendChild(messageText);
    
    feedbackContainer.innerHTML = '';
    feedbackContainer.appendChild(feedbackDiv);
    
    // 3秒后自动消失
    setTimeout(() => {
        feedbackDiv.style.opacity = '0';
        feedbackDiv.style.transition = 'opacity 0.5s';
        setTimeout(() => feedbackDiv.remove(), 500);
    }, 3000);
}

// 设置 Payload（快捷按钮功能）
function setPayload(username, password) {
    const usernameInput = document.getElementById('usernameInput');
    const passwordInput = document.getElementById('passwordInput');
    
    if (usernameInput && passwordInput) {
        usernameInput.value = username;
        passwordInput.value = password;
        updateSQLPreview(username, password);
        
        // 添加视觉反馈
        showFeedback('Payload 已填充！尝试提交查看效果', 'success');
    }
}

// 逐步提示系统
class HintSystem {
    constructor() {
        this.currentStep = 0;
        this.hints = [
            "💡 提示 1: 尝试在用户名中输入一个单引号 '",
            "💡 提示 2: 注意 SQL 注释符 -- 可以注释掉后面的内容",
            "💡 提示 3: OR '1'='1' 是一个永真条件",
            "💡 提示 4: UNION 操作符可以合并两个查询的结果",
            "🎉 完成！你已经理解了 SQL 注入的基本原理"
        ];
    }
    
    nextHint() {
        if (this.currentStep >= this.hints.length) {
            this.currentStep = 0;
        }
        return this.hints[this.currentStep++];
    }
    
    showNextHint() {
        const hint = this.nextHint();
        showFeedback(hint, 'info');
    }
}

// 实例化提示系统
const hintSystem = new HintSystem();

// Payload 预设集合
const payloadPresets = {
    bypassAuth: {
        username: "admin' OR '1'='1' --",
        password: "",
        description: "绕过身份验证"
    },
    unionSelect: {
        username: "' UNION SELECT id, username, email, password_hash, role FROM users --",
        password: "",
        description: "联合查询注入"
    },
    findFlag: {
        username: "' UNION SELECT id, flag_name, flag_value, hint, 'user' FROM hidden_flags --",
        password: "",
        description: "寻找隐藏的 Flag"
    },
    alwaysTrue: {
        username: "' OR 1=1 --",
        password: "",
        description: "永真条件"
    },
    blindInjection: {
        username: "admin' AND (SELECT COUNT(*) FROM users) > 0 --",
        password: "",
        description: "盲注测试"
    }
};

// 应用 Payload 预设
function applyPayloadPreset(presetName) {
    const preset = payloadPresets[presetName];
    if (preset) {
        setPayload(preset.username, preset.password);
        showFeedback(`已加载 Payload: ${preset.description}`, 'success');
    }
}

// 复制 Payload 到剪贴板
function copyToClipboard(text) {
    if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(() => {
            showFeedback('Payload 已复制到剪贴板！', 'success');
        }).catch(err => {
            console.error('复制失败:', err);
            showFeedback('复制失败，请手动复制', 'error');
        });
    } else {
        // 降级方案
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        document.body.appendChild(textarea);
        textarea.select();
        try {
            document.execCommand('copy');
            showFeedback('Payload 已复制到剪贴板！', 'success');
        } catch (err) {
            showFeedback('复制失败，请手动复制', 'error');
        }
        document.body.removeChild(textarea);
    }
}

// 模拟攻击结果可视化
function visualizeAttackResult(successful) {
    const resultContainer = document.getElementById('attackResultContainer');
    if (!resultContainer) return;
    
    resultContainer.innerHTML = '';
    
    const resultDiv = document.createElement('div');
    resultDiv.className = successful ? 'feedback-success' : 'feedback-error';
    
    if (successful) {
        // 创建标题
        const title = document.createElement('h3');
        const icon = document.createElement('i');
        icon.className = 'fas fa-unlock';
        title.appendChild(icon);
        title.appendChild(document.createTextNode(' 攻击成功！'));
        resultDiv.appendChild(title);
        
        // 创建描述段落
        const desc = document.createElement('p');
        desc.textContent = 'SQL 注入成功绕过了身份验证。这展示了漏洞代码的危险性。';
        resultDiv.appendChild(desc);
        
        // 创建后果说明
        const consequences = document.createElement('p');
        const strong = document.createElement('strong');
        strong.textContent = '在真实场景中，这可能导致：';
        consequences.appendChild(strong);
        resultDiv.appendChild(consequences);
        
        // 创建列表
        const list = document.createElement('ul');
        ['未授权访问系统', '窃取敏感数据', '篡改数据库内容'].forEach(text => {
            const li = document.createElement('li');
            li.textContent = text;
            list.appendChild(li);
        });
        resultDiv.appendChild(list);
    } else {
        // 创建标题
        const title = document.createElement('h3');
        const icon = document.createElement('i');
        icon.className = 'fas fa-shield-alt';
        title.appendChild(icon);
        title.appendChild(document.createTextNode(' 安全代码拦截了攻击！'));
        resultDiv.appendChild(title);
        
        // 创建描述段落
        const desc = document.createElement('p');
        desc.textContent = '参数化查询成功防御了 SQL 注入尝试。';
        resultDiv.appendChild(desc);
        
        // 创建防护原因
        const reason = document.createElement('p');
        const strong = document.createElement('strong');
        strong.textContent = '防护原因：';
        reason.appendChild(strong);
        reason.appendChild(document.createTextNode('用户输入被作为数据处理，而不是 SQL 代码。'));
        resultDiv.appendChild(reason);
    }
    
    resultContainer.appendChild(resultDiv);
}

// SQL 查询分析器
function analyzeSQLQuery(query) {
    const analysis = {
        safe: true,
        warnings: [],
        suggestions: []
    };
    
    // 检测字符串拼接
    if (query.includes('f"') || query.includes("f'") || query.includes('+')) {
        analysis.safe = false;
        analysis.warnings.push('⚠️ 检测到字符串拼接，存在 SQL 注入风险');
        analysis.suggestions.push('✓ 使用参数化查询替代字符串拼接');
    }
    
    // 检测 SQL 关键词
    const sqlKeywords = ['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'UNION'];
    const upperQuery = query.toUpperCase();
    
    sqlKeywords.forEach(keyword => {
        if (upperQuery.includes(keyword) && !query.includes('?') && !query.includes('%s')) {
            analysis.safe = false;
            analysis.warnings.push(`⚠️ 发现 ${keyword} 语句但未使用参数化`);
        }
    });
    
    // 检测参数化标记
    if (query.includes('?') || query.includes('%s')) {
        analysis.safe = true;
        analysis.suggestions.push('✓ 已使用参数化查询，安全性良好');
    }
    
    return analysis;
}

// 显示代码安全分析结果
function displayCodeAnalysis(code) {
    const analysis = analyzeSQLQuery(code);
    const analysisContainer = document.getElementById('codeAnalysisContainer');
    
    if (!analysisContainer) return;
    
    analysisContainer.innerHTML = '';
    
    const resultDiv = document.createElement('div');
    resultDiv.className = analysis.safe ? 'feedback-success' : 'feedback-error';
    
    // 安全创建标题
    const title = document.createElement('h4');
    title.textContent = analysis.safe ? '✅ 代码安全' : '❌ 发现安全问题';
    resultDiv.appendChild(title);
    
    if (analysis.warnings.length > 0) {
        const warningDiv = document.createElement('div');
        const warningTitle = document.createElement('strong');
        warningTitle.textContent = '安全警告：';
        warningDiv.appendChild(warningTitle);
        
        const warningList = document.createElement('ul');
        analysis.warnings.forEach(warning => {
            const li = document.createElement('li');
            li.textContent = warning;
            warningList.appendChild(li);
        });
        warningDiv.appendChild(warningList);
        resultDiv.appendChild(warningDiv);
    }
    
    if (analysis.suggestions.length > 0) {
        const suggestionDiv = document.createElement('div');
        const suggestionTitle = document.createElement('strong');
        suggestionTitle.textContent = '建议：';
        suggestionDiv.appendChild(suggestionTitle);
        
        const suggestionList = document.createElement('ul');
        analysis.suggestions.forEach(suggestion => {
            const li = document.createElement('li');
            li.textContent = suggestion;
            suggestionList.appendChild(li);
        });
        suggestionDiv.appendChild(suggestionList);
        resultDiv.appendChild(suggestionDiv);
    }
    
    analysisContainer.appendChild(resultDiv);
}

// 初始化事件监听器
document.addEventListener('DOMContentLoaded', function() {
    // 监听输入框变化
    const usernameInput = document.getElementById('usernameInput');
    const passwordInput = document.getElementById('passwordInput');
    
    if (usernameInput) {
        usernameInput.addEventListener('input', function() {
            updateSQLPreview(this.value, passwordInput ? passwordInput.value : '');
        });
    }
    
    if (passwordInput) {
        passwordInput.addEventListener('input', function() {
            updateSQLPreview(usernameInput ? usernameInput.value : '', this.value);
        });
    }
    
    // 初始化 SQL 预览
    if (usernameInput && passwordInput) {
        updateSQLPreview('', '');
    }
    
    // 添加提示按钮事件
    const hintButton = document.getElementById('showHintButton');
    if (hintButton) {
        hintButton.addEventListener('click', function() {
            hintSystem.showNextHint();
        });
    }
});

// 导出函数供全局使用
window.securityDemo = {
    setPayload,
    applyPayloadPreset,
    copyToClipboard,
    visualizeAttackResult,
    displayCodeAnalysis,
    showFeedback
};
