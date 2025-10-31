'use client'

import { Card, CardContent } from '@/components/ui/card'
import {
  MessageCircle, Upload, Database,
  CheckCircle, FileText, BarChart3, Settings,
  ChevronRight, Sparkles, Zap, Shield
} from 'lucide-react'

export default function UserGuide() {
  // All demos are always active
  const allActive = true

  return (
    <div className="min-h-screen bg-gradient-to-br from-background to-muted p-6">
      <div className="max-w-7xl mx-auto space-y-8">

        {/* Header */}
        <div className="text-center space-y-4">
          <h1 className="text-4xl font-bold bg-gradient-to-r from-primary to-primary/70 bg-clip-text text-transparent">
            辉途智能配方助手 - 使用指南
          </h1>
          <p className="text-lg text-muted-foreground max-w-2xl mx-auto">
            基于 AI 的多动物营养配方系统，支持奶牛、肉牛、猫、狗等多种动物的智能配方优化
          </p>
        </div>

        {/* Quick Start Guide */}
        <Card className="border-primary/20 shadow-lg">
          <CardContent className="p-8">
            <div className="flex items-center gap-3 mb-6">
              <Sparkles className="h-6 w-6 text-primary" />
              <h2 className="text-2xl font-bold">快速开始</h2>
            </div>

            <div className="grid md:grid-cols-4 gap-4">
              {[
                { step: '1', title: '创建会话', desc: '选择动物类型', icon: <MessageCircle className="h-5 w-5" /> },
                { step: '2', title: '上传数据', desc: '导入饲料和牛群信息', icon: <Upload className="h-5 w-5" /> },
                { step: '3', title: '智能对话', desc: '与 AI 营养师交流', icon: <Sparkles className="h-5 w-5" /> },
                { step: '4', title: '查看结果', desc: '获取配方和分析', icon: <CheckCircle className="h-5 w-5" /> }
              ].map((item, idx) => (
                <div key={idx} className="relative">
                  <div className="flex flex-col items-center text-center space-y-3 p-4 rounded-lg border bg-card hover:bg-accent/50 transition-colors">
                    <div className="flex items-center justify-center w-12 h-12 rounded-full bg-primary/10 text-primary">
                      {item.icon}
                    </div>
                    <div className="absolute -top-2 -left-2 w-8 h-8 rounded-full bg-primary text-primary-foreground flex items-center justify-center font-bold text-sm">
                      {item.step}
                    </div>
                    <h3 className="font-semibold">{item.title}</h3>
                    <p className="text-xs text-muted-foreground">{item.desc}</p>
                  </div>
                  {idx < 3 && (
                    <ChevronRight className="hidden md:block absolute top-1/2 -right-5 -translate-y-1/2 h-6 w-6 text-muted-foreground" />
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Feature Demos */}
        <div className="grid lg:grid-cols-2 gap-6">

          {/* Demo 1: Session Creation */}
          <Card className="overflow-hidden">
            <CardContent className="p-6">
              <div className="flex items-center gap-2 mb-4">
                <MessageCircle className="h-5 w-5 text-primary" />
                <h3 className="text-xl font-bold">创建对话会话</h3>
              </div>

              <div className={`demo-container ${allActive ? 'active' : ''}`}>
                <div className="mock-ui">
                  <div className="sidebar-demo">
                    <div className="new-session-btn">
                      <span className="plus-icon">+</span>
                      <span>新建对话</span>
                    </div>
                  </div>

                  <div className="modal-overlay">
                    <div className="animal-selector-modal">
                      <div className="modal-header">选择动物类型</div>
                      <div className="animal-options">
                        <div className="animal-option dairy">
                          <span className="emoji">🐄</span>
                          <span>奶牛 Dairy Cow</span>
                        </div>
                        <div className="animal-option beef">
                          <span className="emoji">🐂</span>
                          <span>肉牛 Beef Cow</span>
                        </div>
                        <div className="animal-option cat">
                          <span className="emoji">🐱</span>
                          <span>猫 Cat</span>
                        </div>
                        <div className="animal-option dog">
                          <span className="emoji">🐶</span>
                          <span>狗 Dog</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="mt-4 space-y-2 text-sm text-muted-foreground">
                <p>• 点击侧边栏的&ldquo;新建对话&rdquo;按钮</p>
                <p>• 选择您要配制的动物类型</p>
                <p>• 系统将创建专属的营养师助手</p>
                <p>• 每个会话绑定单一动物类型</p>
              </div>
            </CardContent>
          </Card>

          {/* Demo 2: File Upload */}
          <Card className="overflow-hidden">
            <CardContent className="p-6">
              <div className="flex items-center gap-2 mb-4">
                <Upload className="h-5 w-5 text-primary" />
                <h3 className="text-xl font-bold">上传数据文件</h3>
              </div>

              <div className={`demo-container ${allActive ? 'active' : ''}`}>
                <div className="mock-ui">
                  <div className="chat-input-demo">
                    <div className="upload-btn-demo">
                      <Upload className="h-4 w-4" />
                    </div>
                    <div className="input-field">输入您的消息...</div>
                  </div>

                  <div className="file-upload-zone">
                    <div className="file-item">
                      <FileText className="h-5 w-5" />
                      <span>牛群信息.xlsx</span>
                      <div className="upload-progress"></div>
                    </div>
                    <div className="file-item delay-1">
                      <FileText className="h-5 w-5" />
                      <span>饲料数据.xlsx</span>
                      <div className="upload-progress"></div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="mt-4 space-y-2 text-sm text-muted-foreground">
                <p>• 点击上传按钮打开文件选择</p>
                <p>• 支持 Excel (.xlsx) 格式</p>
                <p>• 可同时上传多个文件</p>
                <p>• 最大文件大小：10MB</p>
              </div>
            </CardContent>
          </Card>

          {/* Demo 3: Chat Interaction */}
          <Card className="overflow-hidden">
            <CardContent className="p-6">
              <div className="flex items-center gap-2 mb-4">
                <Sparkles className="h-5 w-5 text-primary" />
                <h3 className="text-xl font-bold">AI 对话交互</h3>
              </div>

              <div className={`demo-container ${allActive ? 'active' : ''}`}>
                <div className="mock-ui">
                  <div className="chat-messages-demo">
                    <div className="message user-msg">
                      <div className="message-bubble">
                        请帮我分析这批奶牛的营养需求
                      </div>
                    </div>

                    <div className="message agent-msg">
                      <div className="message-bubble">
                        <div className="typing-indicator">
                          <span></span>
                          <span></span>
                          <span></span>
                        </div>
                        <div className="agent-text">
                          我正在分析您上传的牛群数据...
                        </div>
                      </div>
                    </div>

                    <div className="message tool-msg">
                      <div className="tool-badge">
                        <Zap className="h-3 w-3" />
                        <span>Excel 分析工具</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="mt-4 space-y-2 text-sm text-muted-foreground">
                <p>• 实时流式响应，即时显示</p>
                <p>• 支持停止执行功能</p>
                <p>• 自动工具调用（Excel、配方优化）</p>
                <p>• Enter 发送，Shift+Enter 换行</p>
              </div>
            </CardContent>
          </Card>

          {/* Demo 4: Feedbase Management */}
          <Card className="overflow-hidden">
            <CardContent className="p-6">
              <div className="flex items-center gap-2 mb-4">
                <Database className="h-5 w-5 text-primary" />
                <h3 className="text-xl font-bold">饲料库管理</h3>
              </div>

              <div className={`demo-container ${allActive ? 'active' : ''}`}>
                <div className="mock-ui">
                  <div className="feedbase-demo">
                    <div className="feedbase-filter">
                      <div className="filter-pill active">全部</div>
                      <div className="filter-pill">奶牛</div>
                      <div className="filter-pill">肉牛</div>
                      <div className="filter-pill">猫</div>
                      <div className="filter-pill">狗</div>
                    </div>

                    <div className="feedbase-list">
                      <div className="feedbase-item">
                        <span className="emoji">🐄</span>
                        <span>奶牛饲料库 2024</span>
                      </div>
                      <div className="feedbase-item">
                        <span className="emoji">🐂</span>
                        <span>肉牛基础饲料</span>
                      </div>
                    </div>

                    <div className="feedbase-editor">
                      <div className="editor-header">编辑饲料库</div>
                      <div className="feed-table">
                        <div className="table-row header">
                          <span>饲料名称</span>
                          <span>DM%</span>
                          <span>成本</span>
                        </div>
                        <div className="table-row">
                          <span>苜蓿干草</span>
                          <span>88.5</span>
                          <span>3.2</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div className="mt-4 space-y-2 text-sm text-muted-foreground">
                <p>• 按动物类型筛选饲料库</p>
                <p>• 创建、编辑、删除饲料库</p>
                <p>• 导出为 Excel 格式</p>
                <p>• 支持营养成分自定义</p>
              </div>
            </CardContent>
          </Card>

        </div>

        {/* Features Overview */}
        <Card>
          <CardContent className="p-8">
            <div className="flex items-center gap-3 mb-6">
              <Zap className="h-6 w-6 text-primary" />
              <h2 className="text-2xl font-bold">核心功能</h2>
            </div>

            <div className="grid md:grid-cols-3 gap-6">
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <Shield className="h-5 w-5 text-primary" />
                  <h3 className="font-semibold">多动物支持</h3>
                </div>
                <ul className="space-y-2 text-sm text-muted-foreground ml-7">
                  <li>• 奶牛：NRC 2021 标准</li>
                  <li>• 肉牛：NEm/NEg 系统</li>
                  <li>• 猫：FEDIAF 标准</li>
                  <li>• 狗：FEDIAF 全生命周期营养</li>
               </ul>
              </div>

              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <BarChart3 className="h-5 w-5 text-primary" />
                  <h3 className="font-semibold">智能分析</h3>
                </div>
                <ul className="space-y-2 text-sm text-muted-foreground ml-7">
                  <li>• Excel 数据自动解析</li>
                  <li>• 营养需求计算</li>
                  <li>• 配方优化算法</li>
                  <li>• HTML 可视化报告</li>
                </ul>
              </div>

              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <Settings className="h-5 w-5 text-primary" />
                  <h3 className="font-semibold">管理功能</h3>
                </div>
                <ul className="space-y-2 text-sm text-muted-foreground ml-7">
                  <li>• 用户权限管理</li>
                  <li>• 动物类型权限</li>
                  <li>• 会话历史记录</li>
                  <li>• Token 使用统计</li>
                </ul>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Best Practices */}
        <Card className="border-primary/20">
          <CardContent className="p-8">
            <h2 className="text-2xl font-bold mb-6">最佳实践建议</h2>

            <div className="space-y-4">
              <div className="flex gap-3">
                <CheckCircle className="h-5 w-5 text-primary flex-shrink-0 mt-0.5" />
                <div>
                  <h3 className="font-semibold mb-1">数据准备</h3>
                  <p className="text-sm text-muted-foreground">
                    上传前确保 Excel 文件格式正确，包含必要的营养成分列（DM%、CP、NDF 等）
                  </p>
                </div>
              </div>

              <div className="flex gap-3">
                <CheckCircle className="h-5 w-5 text-primary flex-shrink-0 mt-0.5" />
                <div>
                  <h3 className="font-semibold mb-1">明确需求</h3>
                  <p className="text-sm text-muted-foreground">
                    与 AI 营养师对话时，清晰描述动物状况、营养目标、成本预算等关键信息
                  </p>
                </div>
              </div>

              <div className="flex gap-3">
                <CheckCircle className="h-5 w-5 text-primary flex-shrink-0 mt-0.5" />
                <div>
                  <h3 className="font-semibold mb-1">验证结果</h3>
                  <p className="text-sm text-muted-foreground">
                    AI 生成的配方建议应结合实际情况验证，必要时咨询专业营养师
                  </p>
                </div>
              </div>

              <div className="flex gap-3">
                <CheckCircle className="h-5 w-5 text-primary flex-shrink-0 mt-0.5" />
                <div>
                  <h3 className="font-semibold mb-1">饲料库维护</h3>
                  <p className="text-sm text-muted-foreground">
                    定期更新饲料库中的价格和营养成分数据，确保配方优化的准确性
                  </p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

      </div>

      <style jsx>{`
        .demo-container {
          min-height: 380px;
          border-radius: 8px;
          background: linear-gradient(to bottom, #f8f9fa, #ffffff);
          border: 1px solid #e5e7eb;
          padding: 20px;
          position: relative;
          overflow: hidden;
        }

        .mock-ui {
          position: relative;
          width: 100%;
          height: 100%;
          min-height: 340px;
        }

        /* Session Creation Demo */
        .sidebar-demo {
          position: absolute;
          top: 10px;
          left: 10px;
          width: 150px;
        }

        .new-session-btn {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 8px 12px;
          background: hsl(var(--primary));
          color: white;
          border-radius: 6px;
          font-size: 14px;
          cursor: pointer;
          transition: transform 0.2s;
        }

        .active .new-session-btn {
          animation: btnClick 0.5s ease 0.5s;
        }

        @keyframes btnClick {
          0%, 100% { transform: scale(1); }
          50% { transform: scale(0.95); }
        }

        .plus-icon {
          font-size: 18px;
          font-weight: bold;
        }

        .modal-overlay {
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0, 0, 0, 0);
          display: flex;
          align-items: center;
          justify-content: center;
          pointer-events: none;
          transition: background 0.3s;
        }

        .active .modal-overlay {
          animation: fadeIn 0.3s ease 1s forwards;
        }

        @keyframes fadeIn {
          to {
            background: rgba(0, 0, 0, 0.5);
            pointer-events: all;
          }
        }

        .animal-selector-modal {
          background: white;
          border-radius: 12px;
          padding: 20px;
          box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
          transform: scale(0.8);
          opacity: 0;
          max-width: 360px;
          width: 85%;
        }

        .active .animal-selector-modal {
          animation: modalAppear 0.4s ease 1.3s forwards;
        }

        @keyframes modalAppear {
          to {
            transform: scale(1);
            opacity: 1;
          }
        }

        .modal-header {
          font-size: 18px;
          font-weight: 600;
          margin-bottom: 16px;
          text-align: center;
        }

        .animal-options {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 12px;
        }

        .animal-option {
          padding: 12px;
          border: 2px solid #e5e7eb;
          border-radius: 8px;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 6px;
          font-size: 12px;
          cursor: pointer;
          transition: all 0.2s;
          opacity: 0;
          transform: translateY(10px);
        }

        .active .animal-option {
          animation: optionAppear 0.3s ease forwards;
        }

        .active .animal-option.dairy {
          animation-delay: 1.6s;
        }

        .active .animal-option.beef {
          animation-delay: 1.7s;
        }

        .active .animal-option.cat {
          animation-delay: 1.8s;
        }

        .active .animal-option.dog {
          animation-delay: 1.9s;
        }

        @keyframes optionAppear {
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        .animal-option:hover {
          border-color: hsl(var(--primary));
          background: hsl(var(--primary) / 0.05);
        }

        .animal-option .emoji {
          font-size: 28px;
        }

        /* File Upload Demo */
        .chat-input-demo {
          display: flex;
          gap: 8px;
          align-items: center;
          padding: 12px;
          border: 1px solid #e5e7eb;
          border-radius: 8px;
          margin-bottom: 16px;
        }

        .upload-btn-demo {
          padding: 8px;
          border: 1px solid #e5e7eb;
          border-radius: 6px;
          background: white;
          cursor: pointer;
          transition: background 0.2s;
        }

        .active .upload-btn-demo {
          animation: btnPulse 0.5s ease 0.5s;
        }

        @keyframes btnPulse {
          0%, 100% { transform: scale(1); }
          50% { transform: scale(1.1); background: hsl(var(--primary) / 0.1); }
        }

        .input-field {
          flex: 1;
          padding: 8px;
          color: #9ca3af;
          font-size: 14px;
        }

        .file-upload-zone {
          background: #f9fafb;
          border: 2px dashed #d1d5db;
          border-radius: 8px;
          padding: 20px;
          display: flex;
          flex-direction: column;
          gap: 12px;
          opacity: 0;
        }

        .active .file-upload-zone {
          animation: zoneAppear 0.3s ease 1s forwards;
        }

        @keyframes zoneAppear {
          to { opacity: 1; }
        }

        .file-item {
          display: flex;
          align-items: center;
          gap: 12px;
          padding: 12px;
          background: white;
          border: 1px solid #e5e7eb;
          border-radius: 6px;
          font-size: 14px;
          opacity: 0;
          transform: translateX(-20px);
        }

        .active .file-item {
          animation: fileSlideIn 0.4s ease 1.3s forwards;
        }

        .active .file-item.delay-1 {
          animation-delay: 1.6s;
        }

        @keyframes fileSlideIn {
          to {
            opacity: 1;
            transform: translateX(0);
          }
        }

        .upload-progress {
          margin-left: auto;
          width: 80px;
          height: 4px;
          background: #e5e7eb;
          border-radius: 2px;
          overflow: hidden;
          position: relative;
        }

        .upload-progress::after {
          content: '';
          position: absolute;
          top: 0;
          left: 0;
          height: 100%;
          width: 0%;
          background: hsl(var(--primary));
        }

        .active .file-item .upload-progress::after {
          animation: progressFill 2s ease 1.5s forwards;
        }

        .active .file-item.delay-1 .upload-progress::after {
          animation-delay: 1.8s;
        }

        @keyframes progressFill {
          to { width: 100%; }
        }

        /* Chat Demo */
        .chat-messages-demo {
          display: flex;
          flex-direction: column;
          gap: 12px;
          padding: 12px;
        }

        .message {
          display: flex;
          opacity: 0;
        }

        .active .message {
          animation: messageAppear 0.3s ease forwards;
        }

        .active .message.user-msg {
          animation-delay: 0.5s;
        }

        .active .message.agent-msg {
          animation-delay: 1.2s;
        }

        .active .message.tool-msg {
          animation-delay: 2.5s;
        }

        @keyframes messageAppear {
          to { opacity: 1; }
        }

        .message.user-msg {
          justify-content: flex-end;
        }

        .message-bubble {
          max-width: 80%;
          padding: 12px 16px;
          border-radius: 12px;
          font-size: 14px;
        }

        .user-msg .message-bubble {
          background: hsl(var(--primary));
          color: white;
        }

        .agent-msg .message-bubble {
          background: #f3f4f6;
          color: #1f2937;
        }

        .typing-indicator {
          display: flex;
          gap: 4px;
          margin-bottom: 8px;
        }

        .typing-indicator span {
          width: 6px;
          height: 6px;
          background: #9ca3af;
          border-radius: 50%;
        }

        .active .typing-indicator span {
          animation: typingDot 1.4s infinite;
        }

        .active .typing-indicator span:nth-child(2) {
          animation-delay: 0.2s;
        }

        .active .typing-indicator span:nth-child(3) {
          animation-delay: 0.4s;
        }

        @keyframes typingDot {
          0%, 60%, 100% { transform: translateY(0); }
          30% { transform: translateY(-8px); }
        }

        .agent-text {
          opacity: 0;
        }

        .active .agent-text {
          animation: textFadeIn 0.3s ease 1.8s forwards;
        }

        @keyframes textFadeIn {
          to { opacity: 1; }
        }

        .tool-msg {
          justify-content: center;
        }

        .tool-badge {
          display: flex;
          align-items: center;
          gap: 6px;
          padding: 6px 12px;
          background: #fef3c7;
          color: #92400e;
          border-radius: 16px;
          font-size: 12px;
          font-weight: 500;
        }

        /* Feedbase Demo */
        .feedbase-demo {
          display: grid;
          grid-template-columns: 180px 1fr;
          gap: 16px;
          height: 100%;
        }

        .feedbase-filter {
          display: flex;
          flex-direction: column;
          gap: 6px;
        }

        .filter-pill {
          padding: 8px 12px;
          border: 1px solid #e5e7eb;
          border-radius: 16px;
          font-size: 12px;
          text-align: center;
          cursor: pointer;
          transition: all 0.2s;
          opacity: 0;
          transform: translateX(-10px);
        }

        .active .filter-pill {
          animation: pillSlide 0.2s ease forwards;
        }

        .active .filter-pill:nth-child(1) { animation-delay: 0.3s; }
        .active .filter-pill:nth-child(2) { animation-delay: 0.4s; }
        .active .filter-pill:nth-child(3) { animation-delay: 0.5s; }
        .active .filter-pill:nth-child(4) { animation-delay: 0.6s; }
        .active .filter-pill:nth-child(5) { animation-delay: 0.7s; }

        @keyframes pillSlide {
          to {
            opacity: 1;
            transform: translateX(0);
          }
        }

        .filter-pill.active {
          background: hsl(var(--primary));
          color: white;
          border-color: hsl(var(--primary));
        }

        .feedbase-list {
          display: flex;
          flex-direction: column;
          gap: 8px;
          opacity: 0;
        }

        .active .feedbase-list {
          animation: listAppear 0.3s ease 0.9s forwards;
        }

        @keyframes listAppear {
          to { opacity: 1; }
        }

        .feedbase-item {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 10px;
          border: 1px solid #e5e7eb;
          border-radius: 6px;
          font-size: 13px;
          cursor: pointer;
          transition: background 0.2s;
        }

        .feedbase-item:hover {
          background: #f9fafb;
        }

        .feedbase-item .emoji {
          font-size: 20px;
        }

        .feedbase-editor {
          grid-column: 1 / -1;
          margin-top: 12px;
          opacity: 0;
        }

        .active .feedbase-editor {
          animation: editorSlideUp 0.4s ease 1.5s forwards;
        }

        @keyframes editorSlideUp {
          from {
            opacity: 0;
            transform: translateY(20px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        .editor-header {
          font-weight: 600;
          margin-bottom: 12px;
          font-size: 14px;
        }

        .feed-table {
          border: 1px solid #e5e7eb;
          border-radius: 6px;
          overflow: hidden;
        }

        .table-row {
          display: grid;
          grid-template-columns: 2fr 1fr 1fr;
          gap: 12px;
          padding: 10px 12px;
          font-size: 13px;
          border-bottom: 1px solid #e5e7eb;
        }

        .table-row:last-child {
          border-bottom: none;
        }

        .table-row.header {
          background: #f9fafb;
          font-weight: 600;
        }

        @media (max-width: 768px) {
          .demo-container {
            min-height: 320px;
          }

          .feedbase-demo {
            grid-template-columns: 1fr;
          }

          .feedbase-filter {
            flex-direction: row;
            flex-wrap: wrap;
          }
        }
      `}</style>
    </div>
  )
}
