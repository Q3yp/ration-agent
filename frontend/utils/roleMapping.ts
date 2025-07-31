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
  'supervisor': {
    name: '协调员',
    transitionMessage: '分析任务并处理',
    icon: Brain,
    color: '#1d4ed8', // Blue-700
    bgColor: '#eff6ff border-2',
    customStyles: {
      color: '#1d4ed8',
      backgroundColor: '#eff6ff',
      borderColor: '#93c5fd'
    }
  },
  'search_worker': {
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
  'code_worker': {
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