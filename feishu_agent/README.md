# 5寸照片打印 Agent

飞书机器人，自动接收图片生成 Word 文档并打印。

## 功能

- 接收飞书图片，生成 5 寸照片 Word 文档
- 自动转换为 PDF 并打印
- 打印完成后发送通知

## 启动

```bash
cd /Users/gotta/agents/feishu_agent
./venv/bin/python feishu_agent.py
```

## 服务管理

**启动服务：**
```bash
launchctl load /Users/gotta/Library/LaunchAgents/com.5cunprint.agent.plist
```

**停止服务：**
```bash
launchctl unload /Users/gotta/Library/LaunchAgents/com.5cunprint.agent.plist
```

**查看状态：**
```bash
launchctl list | grep 5cunprint
```

## 使用流程

1. 在飞书对机器人说「5寸照片打印」
2. 发送要打印的图片
3. 说「可以打印」生成 Word 并打印
4. 说「取消」或「退出打印」放弃当前任务

## 目录结构

```
~/5cun-print/
├── input_images/   # 输入图片目录
└── output/         # 生成的 Word 文档
```

## 日志

- 服务日志：`/Users/gotta/agents/feishu_agent/agent.log`
- 错误日志：`/Users/gotta/agents/feishu_agent/agent.error.log`
