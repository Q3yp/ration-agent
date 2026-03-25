import { Locale } from '@/lib/i18n/locales'

type QuickStepIcon = 'message' | 'upload' | 'sparkles' | 'check'

type QuickStep = {
  icon: QuickStepIcon
  title: string
  description: string
}

type DemoCopy = {
  title: string
  bullets: string[]
  buttonLabel?: string
  modalTitle?: string
  animalOptions?: string[]
  fileNames?: string[]
  inputPlaceholder?: string
  userMessage?: string
  agentMessage?: string
  toolLabel?: string
  filters?: string[]
  feedList?: string[]
  tableHeaders?: string[]
  sampleFeed?: string
  editorHeader?: string
}

type FeatureBlock = {
  title: string
  bullets: string[]
}

type PracticeTip = {
  title: string
  description: string
}

export interface UserGuideCopy {
  title: string
  subtitle: string
  quickStartHeading: string
  quickSteps: QuickStep[]
  demos: {
    session: DemoCopy
    upload: DemoCopy
    chat: DemoCopy
    feedbase: DemoCopy
  }
  featuresHeading: string
  features: FeatureBlock[]
  bestPracticesHeading: string
  bestPractices: PracticeTip[]
}

export const userGuideCopy: Record<Locale, UserGuideCopy> = {
  'zh-CN': {
    title: '辉途智能配方助手 - 使用指南',
    subtitle: '基于 AI 的多动物营养配方系统，支持奶牛、肉牛、猫、狗等多种动物的智能配方优化',
    quickStartHeading: '快速开始',
    quickSteps: [
      { icon: 'message', title: '创建会话', description: '选择动物类型' },
      { icon: 'upload', title: '上传数据', description: '导入饲料和牛群信息' },
      { icon: 'sparkles', title: '智能对话', description: '与 AI 营养师交流' },
      { icon: 'check', title: '查看结果', description: '获取配方和分析' }
    ],
    demos: {
      session: {
        title: '创建对话会话',
        bullets: [
          '点击侧边栏的“新建对话”按钮',
          '选择您要配制的动物类型',
          '系统将创建专属的营养师助手',
          '每个会话绑定单一动物类型'
        ],
        buttonLabel: '新建对话',
        modalTitle: '选择动物类型',
        animalOptions: ['奶牛 Dairy Cow', '肉牛 Beef Cow', '猫 Cat', '狗 Dog']
      },
      upload: {
        title: '上传数据文件',
        bullets: [
          '点击上传按钮打开文件选择',
          '支持 Excel (.xlsx) 格式',
          '可同时上传多个文件',
          '最大文件大小 10MB'
        ],
        inputPlaceholder: '输入您的消息...',
        fileNames: ['牛群信息.xlsx', '饲料数据.xlsx']
      },
      chat: {
        title: 'AI 对话交互',
        bullets: [
          '实时流式响应，即时显示',
          '支持停止执行功能',
          '自动工具调用（Excel、配方优化）',
          'Enter 发送，Shift+Enter 换行'
        ],
        userMessage: '请帮我分析这批奶牛的营养需求',
        agentMessage: '我正在分析您上传的牛群数据...',
        toolLabel: 'Excel 分析工具'
      },
      feedbase: {
        title: '饲料库管理',
        bullets: [
          '按动物类型筛选饲料库',
          '创建、编辑、删除饲料库',
          '导出为 Excel 格式',
          '支持营养成分自定义'
        ],
        filters: ['全部', '奶牛', '肉牛', '猫', '狗'],
        feedList: ['奶牛饲料库 2024', '肉牛基础饲料'],
        tableHeaders: ['饲料名称', 'DM%', '成本'],
        sampleFeed: '苜蓿干草',
        editorHeader: '编辑饲料库'
      }
    },
    featuresHeading: '核心功能',
    features: [
      {
        title: '多动物支持',
        bullets: ['奶牛：NRC 2021 标准', '肉牛：NEm/NEg 系统', '猫：FEDIAF 标准', '狗：FEDIAF 全生命周期营养']
      },
      {
        title: '智能分析',
        bullets: ['Excel 数据自动解析', '营养需求计算', '配方优化算法', 'HTML 可视化报告']
      },
      {
        title: '管理功能',
        bullets: ['用户权限管理', '动物类型权限', '会话历史记录', 'Token 使用统计']
      }
    ],
    bestPracticesHeading: '最佳实践建议',
    bestPractices: [
      {
        title: '数据准备',
        description: '上传前确保 Excel 文件格式正确，包含必要的营养成分列（DM%、CP、NDF 等）'
      },
      {
        title: '明确需求',
        description: '与 AI 营养师对话时，清晰描述动物状况、营养目标、成本预算等关键信息'
      },
      {
        title: '验证结果',
        description: 'AI 生成的配方建议应结合实际情况验证，必要时咨询专业营养师'
      },
      {
        title: '饲料库维护',
        description: '定期更新饲料库中的价格和营养成分数据，确保配方优化的准确性'
      }
    ]
  },
  'en-US': {
    title: 'Wuitu Nutrition Copilot – User Guide',
    subtitle: 'An AI-driven formulation system for dairy, beef, and companion animals, delivering accurate feed plans end to end.',
    quickStartHeading: 'Getting started',
    quickSteps: [
      { icon: 'message', title: 'Create a session', description: 'Pick an animal type' },
      { icon: 'upload', title: 'Upload data', description: 'Import feed and herd files' },
      { icon: 'sparkles', title: 'Chat with AI', description: 'Discuss goals with the nutritionist' },
      { icon: 'check', title: 'Review results', description: 'Receive the formulation and analysis' }
    ],
    demos: {
      session: {
        title: 'Create a conversation',
        bullets: [
          'Click “New session” in the sidebar',
          'Choose the animal you want to formulate for',
          'A dedicated nutrition agent is prepared instantly',
          'Each session stays focused on one animal type'
        ],
        buttonLabel: 'New session',
        modalTitle: 'Choose animal type',
        animalOptions: ['Dairy Cow', 'Beef Cow', 'Cat', 'Dog']
      },
      upload: {
        title: 'Upload source files',
        bullets: [
          'Use the upload button to select files',
          'Excel (.xlsx) templates are supported',
          'Upload multiple files at once',
          'Maximum size per file: 10 MB'
        ],
        inputPlaceholder: 'Type your message...',
        fileNames: ['herd_data.xlsx', 'feed_library.xlsx']
      },
      chat: {
        title: 'AI conversation flow',
        bullets: [
          'Streaming responses for instant feedback',
          'Stop execution at any time',
          'Automatic tool calls (Excel parsing, optimization)',
          'Press Enter to send, Shift+Enter for a new line'
        ],
        userMessage: 'Help me assess the nutrition plan for this dairy herd',
        agentMessage: 'Reviewing the herd data you uploaded…',
        toolLabel: 'Excel analysis tool'
      },
      feedbase: {
        title: 'Manage feedbases',
        bullets: [
          'Filter feedbases by animal type',
          'Create, edit, or remove feedbases',
          'Export the database as Excel',
          'Customize nutrient profiles freely'
        ],
        filters: ['All', 'Dairy', 'Beef', 'Cat', 'Dog'],
        feedList: ['Dairy Feedbase 2024', 'Beef Starter Library'],
        tableHeaders: ['Feed', 'DM%', 'Cost'],
        sampleFeed: 'Alfalfa hay',
        editorHeader: 'Feedbase editor'
      }
    },
    featuresHeading: 'Key capabilities',
    features: [
      {
        title: 'Multi-species support',
        bullets: ['Dairy cow – NRC 2021', 'Beef cattle – NEm/NEg', 'Cat – FEDIAF nutrient profiles', 'Dog – FEDIAF lifecycle nutrition']
      },
      {
        title: 'Intelligent analysis',
        bullets: ['Automatic Excel ingestion', 'Nutrient requirement calculations', 'Optimization algorithms', 'Rich HTML reporting']
      },
      {
        title: 'Management tools',
        bullets: ['User permissions', 'Animal-type entitlements', 'Session history tracking', 'Token usage monitoring']
      }
    ],
    bestPracticesHeading: 'Best practices',
    bestPractices: [
      {
        title: 'Prep your data',
        description: 'Ensure Excel files include required nutrient columns (DM, CP, NDF, etc.) before uploading.'
      },
      {
        title: 'State the goal clearly',
        description: 'Share animal status, nutrition targets, and budget constraints so the AI can respond accurately.'
      },
      {
        title: 'Validate the output',
        description: 'Review AI-generated diets against on-farm conditions and consult professionals when needed.'
      },
      {
        title: 'Maintain feedbases',
        description: 'Regularly update feed costs and analyses to keep optimization results reliable.'
      }
    ]
  }
}

export type { QuickStepIcon }
