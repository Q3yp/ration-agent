import { Locale } from '@/lib/i18n/locales'

interface FeedbaseCommonCopy {
  animals: Record<string, { label: string; emoji: string }>
}

interface FeedbaseManagerCopy {
  loading: string
  errorPrefix: string
  retry: string
  newFeedbaseName: string
  confirmDelete: string
  createButton: string
  sidebarTitle: string
  emptyStateTitle: string
  emptyStateDescription: string
  createPrimary: string
}

interface FeedbaseListCopy {
  emptyTitle: string
  emptyDescription: string
  systemTag: string
  viewOnly: string
  clickToEdit: string
  export: string
  delete: string
}

interface FeedbaseEditorCopy {
  namePlaceholder: string
  validationName: string
  systemBadge: string
  cancel: string
  close: string
  save: string
  saving: string
  saveError: string
  feedListTitle: (count: number) => string
  feedSummary: (dm: number, cost: number) => string
  deleteFeedTooltip: (name: string) => string
  editHeading: (name: string) => string
  selectFeedTitle: string
  selectFeedDescription: string
  selectFeedDescriptionReadOnly: string
  addFeedPrimary: string
  addFeed: string
  emptyFeedTitle: string
  emptyFeedDescription: string
  newFeedPrefix: string
}

interface FeedEditorCopy {
  title: string
  basicInfo: string
  nameLabel: string
  namePlaceholder: string
  dmLabel: string
  costLabel: string
  nutrientsTitle: string
  nutrientCount: (count: number) => string
  noNutrients: string
  addNutrientHint: string
  deleteTooltip: (name: string) => string
  nutrientNamePlaceholder: string
  addButton: string
}

interface FeedbaseCopy {
  common: FeedbaseCommonCopy
  manager: FeedbaseManagerCopy
  list: FeedbaseListCopy
  editor: FeedbaseEditorCopy
  feedEditor: FeedEditorCopy
}

const feedbaseCopy: Record<Locale, FeedbaseCopy> = {
  'zh-CN': {
    common: {
      animals: {
        all: { label: '全部', emoji: '🌐' },
        dairy_cow: { label: '奶牛', emoji: '🐄' },
        beef_cow: { label: '肉牛', emoji: '🐂' },
        cat: { label: '猫', emoji: '🐱' },
        dog: { label: '狗', emoji: '🐶' }
      }
    },
    manager: {
      loading: '正在加载饲料库...',
      errorPrefix: '错误',
      retry: '重试',
      newFeedbaseName: '新饲料库',
      confirmDelete: '确定要删除饲料库 "{{name}}" 吗？此操作不可撤销。',
      createButton: '新建',
      sidebarTitle: '饲料库列表',
      emptyStateTitle: '开始管理饲料库',
      emptyStateDescription: '选择左侧现有的饲料库进行编辑，或创建一个全新的饲料库',
      createPrimary: '创建新饲料库'
    },
    list: {
      emptyTitle: '暂无饲料库',
      emptyDescription: '点击上方的「新建」按钮创建饲料库',
      systemTag: '系统',
      viewOnly: '点击查看（只读）',
      clickToEdit: '点击编辑饲料库',
      export: '导出',
      delete: '删除'
    },
    editor: {
      namePlaceholder: '饲料库名称',
      validationName: '请输入饲料库名称',
      systemBadge: '系统饲料库（只读）',
      cancel: '取消',
      close: '关闭',
      save: '保存',
      saving: '保存中...',
      saveError: '保存失败',
      feedListTitle: (count) => `饲料列表 (${count})`,
      feedSummary: (dm, cost) => `DM: ${dm}% | 成本: ¥${cost}/kg`,
      deleteFeedTooltip: (name) => `删除饲料 ${name}`,
      editHeading: (name) => `编辑: ${name}`,
      selectFeedTitle: '选择饲料进行编辑',
      selectFeedDescription: '从左侧列表中选择一个饲料进行编辑，或添加新的饲料',
      selectFeedDescriptionReadOnly: '从左侧列表中选择一个饲料查看详情',
      addFeedPrimary: '添加新饲料',
      addFeed: '添加饲料',
      emptyFeedTitle: '暂无饲料',
      emptyFeedDescription: '点击上方按钮添加饲料',
      newFeedPrefix: '新饲料'
    },
    feedEditor: {
      title: '饲料详细信息',
      basicInfo: '基本信息',
      nameLabel: '饲料名称',
      namePlaceholder: '请输入饲料名称',
      dmLabel: '干物质含量 (%)',
      costLabel: '成本 (¥/kg)',
      nutrientsTitle: '营养成分',
      nutrientCount: (count) => `${count} 项`,
      noNutrients: '暂无营养成分',
      addNutrientHint: '使用下方输入框添加营养成分',
      deleteTooltip: (name) => `删除 ${name}`,
      nutrientNamePlaceholder: '输入营养成分名称（如：crude_protein）',
      addButton: '添加'
    }
  },
  'en-US': {
    common: {
      animals: {
        all: { label: 'All', emoji: '🌐' },
        dairy_cow: { label: 'Dairy Cow', emoji: '🐄' },
        beef_cow: { label: 'Beef Cow', emoji: '🐂' },
        cat: { label: 'Cat', emoji: '🐱' },
        dog: { label: 'Dog', emoji: '🐶' }
      }
    },
    manager: {
      loading: 'Loading feedbases...',
      errorPrefix: 'Error',
      retry: 'Retry',
      newFeedbaseName: 'New Feedbase',
      confirmDelete: 'Delete feedbase "{{name}}"? This action cannot be undone.',
      createButton: 'Create',
      sidebarTitle: 'Feedbase library',
      emptyStateTitle: 'Manage your feedbases',
      emptyStateDescription: 'Select a feedbase on the left to edit, or create a brand new one.',
      createPrimary: 'Create feedbase'
    },
    list: {
      emptyTitle: 'No feedbases yet',
      emptyDescription: 'Use the “Create” button above to add your first feedbase',
      systemTag: 'System',
      viewOnly: 'View details (read-only)',
      clickToEdit: 'Click to edit feedbase',
      export: 'Export',
      delete: 'Delete'
    },
    editor: {
      namePlaceholder: 'Feedbase name',
      validationName: 'Enter a feedbase name',
      systemBadge: 'System feedbase (read-only)',
      cancel: 'Cancel',
      close: 'Close',
      save: 'Save',
      saving: 'Saving...',
      saveError: 'Failed to save feedbase',
      feedListTitle: (count) => `Feeds (${count})`,
      feedSummary: (dm, cost) => `DM: ${dm}% | Cost: ¥${cost}/kg`,
      deleteFeedTooltip: (name) => `Remove feed ${name}`,
      editHeading: (name) => `Editing: ${name}`,
      selectFeedTitle: 'Select a feed to edit',
      selectFeedDescription: 'Choose a feed from the left to edit, or add a new one.',
      selectFeedDescriptionReadOnly: 'Choose a feed on the left to view its details.',
      addFeedPrimary: 'Add feed',
      addFeed: 'Add feed',
      emptyFeedTitle: 'No feeds yet',
      emptyFeedDescription: 'Use the button above to add a feed',
      newFeedPrefix: 'Feed'
    },
    feedEditor: {
      title: 'Feed details',
      basicInfo: 'Basic information',
      nameLabel: 'Feed name',
      namePlaceholder: 'Enter feed name',
      dmLabel: 'Dry matter (%)',
      costLabel: 'Cost (¥/kg)',
      nutrientsTitle: 'Nutrient profile',
      nutrientCount: (count) => `${count} items`,
      noNutrients: 'No nutrients yet',
      addNutrientHint: 'Use the inputs below to add nutrient entries',
      deleteTooltip: (name) => `Delete ${name}`,
      nutrientNamePlaceholder: 'Enter nutrient name (e.g. crude_protein)',
      addButton: 'Add'
    }
  }
}

export function getFeedbaseCopy(locale: Locale): FeedbaseCopy {
  return feedbaseCopy[locale]
}
