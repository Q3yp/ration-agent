import { Search, Code, Brain, User } from 'lucide-react'

export interface RoleInfo {
  name: string
  transitionMessage: string
  icon: typeof Search
  color: string
  bgColor: string
  customStyles?: {
    color: string
    backgroundColor: string
    borderColor: string
  }
}

export const roleMapping: Record<string, RoleInfo> = {
  'nutritionist': {
    name: '营养师',
    transitionMessage: '继续作业',
    icon: Brain,
    color: '#1d4ed8', // Blue-700
    bgColor: '#eff6ff border-2',
    customStyles: {
      color: '#1d4ed8',
      backgroundColor: '#eff6ff',
      borderColor: '#93c5fd'
    }
  },
  'researcher': {
    name: '搜索专员',
    transitionMessage: '开始搜索和研究',
    icon: Search,
    color: '#7c3aed', // Violet-600
    bgColor: '#f5f3ff border-2',
    customStyles: {
      color: '#7c3aed',
      backgroundColor: '#f5f3ff',
      borderColor: '#c4b5fd'
    }
  },
  'coder': {
    name: '代码专员',
    transitionMessage: '处理代码和数据分析',
    icon: Code,
    color: '#ea580c', // Orange-600
    bgColor: '#fff7ed border-2',
    customStyles: {
      color: '#ea580c',
      backgroundColor: '#fff7ed',
      borderColor: '#fed7aa'
    }
  },
  'start': {
    name: '开始',
    transitionMessage: '开始处理请求',
    icon: User,
    color: '#374151', // Gray-700
    bgColor: '#f9fafb border-2',
    customStyles: {
      color: '#374151',
      backgroundColor: '#f9fafb',
      borderColor: '#d1d5db'
    }
  },
  '__end__': {
    name: '完成',
    transitionMessage: '任务处理完成',
    icon: User,
    color: '#16a34a', // Green-600
    bgColor: '#f0fdf4 border-2',
    customStyles: {
      color: '#16a34a',
      backgroundColor: '#f0fdf4',
      borderColor: '#bbf7d0'
    }
  },
  'end': {
    name: '完成',
    transitionMessage: '任务处理完成',
    icon: User,
    color: '#16a34a', // Green-600
    bgColor: '#f0fdf4 border-2',
    customStyles: {
      color: '#16a34a',
      backgroundColor: '#f0fdf4',
      borderColor: '#bbf7d0'
    }
  }
}

export function getRoleInfo(role: string): RoleInfo {
  return roleMapping[role] || {
    name: role,
    transitionMessage: `切换到 ${role}`,
    icon: Brain,
    color: '#374151', // Gray-700
    bgColor: '#f9fafb border-2',
    customStyles: {
      color: '#374151',
      backgroundColor: '#f9fafb',
      borderColor: '#d1d5db'
    }
  }
}

// Tool name mapping to Chinese
export const toolNameMapping: Record<string, string> = {
  // Core tools
  'bash_command_for_session': '执行命令',
  'create_artifact': '创建可视化',
  'artifact_tool': '创建可视化',

  // File management
  'write_file': '写入文件',
  'list_directory': '列出目录',

  // Excel tools
  'excel_metadata': 'Excel元数据',
  'excel_query': 'Excel查询',
  'read_excel': '读取Excel',
  'read_excel_file': '读取Excel文件',
  'write_excel_file': '写入Excel文件',
  'analyze_excel_data': '分析Excel数据',

  // Search tools
  'duckduckgo_search': '网页搜索',
  'duckduckgo_news_search': '新闻搜索',
  'search_knowledge_base': '知识库搜索',
  'research_topic_comprehensive': '综合研究',
  'search_and_crawl': '搜索抓取',

  // Web crawling
  'crawl_website': '网页抓取',
  'crawl_multiple_urls': '批量抓取',

  // Formulation tools
  'add_feed': '添加饲料',
  'check_feeds': '检查饲料',
  'formulate_ration': '配方制作',
  'export_formulation': '导出配方',
  'list_feed_bases': '饲料库列表',

  // NASEM tools
  'predict_dairy_requirements': '预测营养需求',
  'evaluate_diet_with_nasem': '评估日粮',

  // Fallback
  'unknown': '未知工具'
}

export function getToolName(toolName: string): string {
  return toolNameMapping[toolName] || toolName
}