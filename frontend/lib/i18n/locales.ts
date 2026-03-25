export type Locale = 'zh-CN' | 'en-US'

export const supportedLocales: Locale[] = ['zh-CN', 'en-US']
export const defaultLocale: Locale = 'zh-CN'

interface TranslationTree {
  [key: string]: string | string[] | TranslationTree
}

export const translations: Record<Locale, TranslationTree> = {
  'zh-CN': {
    common: {
      appName: '辉途智能配方助手',
      welcomeGeneric: '欢迎使用',
      welcomeUser: '欢迎，{{name}}',
      buttons: {
        login: '登录',
        logout: '退出登录',
        register: '注册账号',
        goToApp: '进入应用',
        getStarted: '开始使用',
        goBack: '返回',
        retry: '重试',
        confirm: '确认',
        cancel: '取消',
        delete: '删除',
        deleteAll: '全部删除',
        submit: '提交',
      },
      statuses: {
        loading: '加载中...',
        connecting: '正在连接...',
        connected: '已连接',
        error: '连接错误',
        historyPrompt: '请选择或创建一个对话',
      },
      localeNames: {
        'zh-CN': '简体中文',
        'en-US': 'English',
      },
    },
    landing: {
      heroTitle: 'AI 驱动的奶牛日粮配方系统',
      heroSubtitle: '集成 NASEM 2021 第八版奶牛营养需求模型，通过自然语言交互完成营养需求计算、日粮优化与饲料评估',
      enterSystem: '进入系统',
      modelPortal: '营养模型门户',
      capabilitiesTitle: '系统能力',
      capabilityConversationTitle: '自然语言交互',
      capabilityConversationDescription: '通过对话描述动物参数与配方目标，系统自动调用 NASEM 模型完成计算，无需手动输入表格或编程',
      capabilityModelTitle: 'NASEM 2021 模型',
      capabilityModelDescription: '内置完整 NASEM 2021 奶牛营养需求模型与饲料库（284 种饲料，81 个营养参数），支持自定义饲料数据',
      capabilityWorkflowTitle: '配方优化',
      capabilityWorkflowDescription: '使用 SLSQP 优化器进行日粮配方，支持成本最小化、营养约束设定，结果可导出为报告',
    },
    auth: {
      loginTitle: '辉途智能配方助手 登录',
      emailPlaceholder: '邮箱地址',
      usernamePlaceholder: '用户名',
      passwordPlaceholder: '密码',
      phonePlaceholder: '手机号码',
      smsCodePlaceholder: '短信验证码',
      registerLink: '没有账号？立即注册',
      loggingIn: '登录中...',
      or: '或',
      continueWithGoogle: '使用 Google 登录',
      googleLoginError: '无法连接到 Google 登录，请稍后再试',
      googleProcessing: '正在处理 Google 登录，请稍候...',
      googleOAuthError: 'Google 登录失败：{{message}}',
      googleMissingParams: '缺少 Google 返回的授权信息，请重试。',
      googleExchangeFailed: '无法完成 Google 登录，请稍后再试。',
      googleNoToken: 'Google 登录未返回有效凭证，请重试。',
      googleGenericError: '处理 Google 登录时发生错误，请稍后再试。',
      googleOnlyNote: '无法使用 Google 登录？可前往短信注册页面，使用验证码创建账号。',
      googleInitError: 'Google 登录初始化失败，请刷新页面重试。',
      googleMissingClientId: '未配置 Google 登录客户端 ID，请联系管理员。',
      accountPlaceholder: '账号 / 邮箱 / 手机号',
      accountInvalid: '请输入有效的账号信息。',
      accountRequired: '账号不能为空。',
      passwordRequired: '请输入密码。',
      passwordTooShort: '密码至少需要 8 位字符。',
      registerTitle: '注册账号',
      confirmPasswordPlaceholder: '确认密码',
      registering: '注册中...',
      haveAccount: '已有账号？前往登录',
      smsSendCode: '获取验证码',
      smsResendIn: '{{seconds}} 秒后可重发',
      smsResend: '重新发送验证码',
      smsCodeSent: '验证码已发送，请注意查收。',
      smsCodeFailed: '验证码发送失败，请稍后再试。',
      smsRegisterTitle: '短信注册',
      smsRegisterDescription: '仅支持中国大陆手机号，未填写国际区号的 11 位号码将自动补全 +86。',
      smsRegisterSuccess: '注册成功，正在跳转...',
      smsRegisterFailed: '短信注册失败，请稍后再试。',
      smsAutoCountryHint: '如未填写国际区号，11 位手机号会自动补全 +86。',
      smsInvalidPhone: '目前仅支持 +86 手机号码，请确认后重试。',
      smsMissingFields: '请填写手机号和验证码。',
    },
    chat: {
      guide: '使用指南',
      feedbase: '饲料库管理',
      admin: '用户管理',
      newConversation: '新对话',
      selectPrompt: '请选择或创建一个对话',
      localeToggleLabel: '界面语言',
      tokenUsageLabel: '对话长度',
      inputPlaceholder: '输入您的消息...',
      thinking: '思考中...',
      thinkingStopped: '思考内容',
      responding: '正在输入...',
      tierLabel: '账户等级',
      tierBadges: {
        free: '免费版',
        paid: '专业版',
      },
      freeTierSessionHint: '免费版仅支持猫狗对话，且同一时间只能保留一个会话，对话长度限 50,000 tokens。',
      promptLimitTitle: '已达到会话上限',
      promptLimitBody: '当前对话的上下文已超过免费版 50,000 tokens 限制。请开启新的对话或升级账户以继续使用。',
      promptLimitCTA: '了解升级方案',
      promptLimitDismiss: '稍后再说',
      askedQuestions: '询问',
      userResponse: '您的回复',
      userInputPrefix: '回复询问',
    },
    planUpgrade: {
      title: '选择适合您的方案',
      subtitle: '解锁更多功能，提升使用体验',
      comingSoon: '即将推出',
      free: {
        name: '免费版',
        price: '¥0',
        period: '永久免费',
        features: [
          '系统默认饲料库',
          '同时 1 个会话',
          '50,000 tokens 上下文限制',
          '仅支持猫狗类型',
        ],
      },
      pro: {
        name: '专业版',
        price: '敬请期待',
        period: '按月订阅',
        features: [
          '自定义饲料库创建',
          '无限会话数量',
          '100,000 tokens 上下文限制',
          '真实兽医咨询服务（可能产生额外费用）',
          '多模态问诊（疾病预识别）',
          '每月消息限额',
        ],
      },
      enterprise: {
        name: '企业版',
        price: '联系销售',
        period: '按需定制',
        features: [
          '支持所有畜禽类型（奶牛、肉牛等）',
          '商业营养模型集成',
          '智能体定制化',
          '按使用量付费',
          '专属技术支持',
          '企业级 SLA 保障',
        ],
      },
    },
    sidebar: {
      title: '对话列表',
      newChat: '新建对话',
      deleteAll: '清空',
      deleteConfirm: '您确定要删除这个对话吗？',
      deleteDescription: '此操作无法撤销，将永久删除此对话。',
      deleteAllConfirm: '您确定要删除所有对话吗？这个操作不可恢复。',
      deleteAllDescription: '此操作无法撤销，将永久删除您的所有对话。',
    },
    fileUpload: {
      uploading: '上传中...',
      attachFile: '附加文件',
      removeFile: '移除文件',
      fileUploaded: '文件上传',
      filesCount: '{{count}} 个',
      fileTypesHint: '.txt, .py, .js, .json, .csv, .md, .html, .css, .xml, .yaml, .xlsx (最大 10MB)',
    },
    animalTypes: {
      selectTitle: '选择动物类型',
      loading: '加载中...',
      create: '创建对话',
      dairy_cow: '奶牛',
      beef_cow: '肉牛',
      cat: '猫',
      dog: '狗',
    },
    feedbases: {
      title: '饲料库管理',
      back: '返回对话',
      freeTierNotice: '免费版仅能使用系统默认饲料库。升级即可创建和编辑自定义饲料库。',
    },
    guide: {
      back: '返回对话',
    },
    admin: {
      back: '返回对话',
      userManagement: '用户管理',
      feedbackManagement: '反馈管理',
      feedbackTitle: '反馈管理',
      unknownUser: '未知用户',
      viewSession: '查看会话',
      sessionHistory: '会话历史',
      noFeedbacks: '暂无反馈',
      sessionId: '会话 ID: {{id}}',
      errorFetch: '获取反馈失败',
      errorNetwork: '网络错误',
      close: '关闭',
    },
    protectedRoute: {
      deniedTitle: '访问被拒绝',
      deniedDescription: '您没有权限访问此页面。',
    },
    register: {
      success: '注册成功，请前往登录。',
      passwordMismatch: '两次输入的密码不一致',
    },
    errors: {
      networkRetry: '多次重试失败，请检查网络连接或刷新页面',
      downloadFailed: '下载失败：HTTP {{code}}',
    },
    feedback: {
      buttonLabel: '反馈',
      dialogTitle: '提交反馈',
      dialogDescription: '请提供您对本次对话的反馈，帮助我们改进。',
      placeholder: '在此输入您的反馈...',
      submit: '提交',
      success: '反馈提交成功',
      error: '提交反馈失败',
    },
    artifact: {
      viewDynamicContent: '✨ 查看动态内容',
      htmlDynamicContent: 'HTML 动态内容',
      viewSuggestion: '💡 查看建议',
      defaultTitle: 'HTML 内容',
      recipeSuggestionPrefix: '建议 - ',
      recipeAnalysisTitle: 'AI 营养师分析与建议',
      suggestionTitle: '💡 配方建议',
    },
    fileExport: {
      downloadRecipe: '✨ 下载报告',
      format: '{{type}} 格式',
      readyDownload: '准备下载',
      recipeSuggestion: '配方建议',
    },
  },
  'en-US': {
    common: {
      appName: 'Wuitu Nutrition Copilot',
      welcomeGeneric: 'Welcome',
      welcomeUser: 'Welcome, {{name}}',
      buttons: {
        login: 'Log In',
        logout: 'Log Out',
        register: 'Create Account',
        goToApp: 'Go to App',
        getStarted: 'Get Started',
        goBack: 'Back',
        retry: 'Retry',
        confirm: 'Confirm',
        cancel: 'Cancel',
        delete: 'Delete',
        deleteAll: 'Delete All',
        submit: 'Submit',
      },
      statuses: {
        loading: 'Loading...',
        connecting: 'Connecting...',
        connected: 'Connected',
        error: 'Connection error',
        historyPrompt: 'Select or create a conversation',
      },
      localeNames: {
        'zh-CN': '简体中文',
        'en-US': 'English',
      },
    },
    landing: {
      heroTitle: 'AI-Driven Dairy Ration Formulation',
      heroSubtitle: 'Integrates the NASEM 2021 (8th Ed.) Nutrient Requirements of Dairy Cattle model with a conversational AI interface for requirement calculation, ration optimization, and diet evaluation',
      enterSystem: 'Enter',
      modelPortal: 'Nutrition Model Portal',
      capabilitiesTitle: 'Capabilities',
      capabilityConversationTitle: 'Natural Language Interface',
      capabilityConversationDescription: 'Describe animal parameters and formulation goals through conversation. The system invokes NASEM model calculations automatically, no manual data entry or programming required.',
      capabilityModelTitle: 'NASEM 2021 Model',
      capabilityModelDescription: 'Full implementation of the NASEM 2021 dairy cattle nutrient requirements model with integrated feed library (284 feeds, 81 nutrient parameters). Supports custom feed data.',
      capabilityWorkflowTitle: 'Ration Optimization',
      capabilityWorkflowDescription: 'SLSQP-based diet optimization with configurable objectives (cost minimization, nutrient constraints). Results exportable as detailed reports.',
    },
    auth: {
      loginTitle: 'Log in to Wuitu Nutrition Copilot',
      emailPlaceholder: 'Email address',
      usernamePlaceholder: 'Username',
      passwordPlaceholder: 'Password',
      phonePlaceholder: 'Phone number',
      smsCodePlaceholder: 'SMS verification code',
      registerLink: "Don't have an account? Sign up",
      loggingIn: 'Signing in...',
      or: 'or',
      continueWithGoogle: 'Continue with Google',
      googleLoginError: 'Unable to start Google login. Please try again.',
      googleProcessing: 'Finishing Google sign-in, please wait...',
      googleOAuthError: 'Google sign-in failed: {{message}}',
      googleMissingParams: 'Missing authorization data from Google. Please try again.',
      googleExchangeFailed: 'Unable to complete Google sign-in. Please try again later.',
      googleNoToken: 'Google sign-in did not return a valid credential. Please try again.',
      googleGenericError: 'Something went wrong while completing Google sign-in. Please try again.',
      googleOnlyNote: 'Prefer another method? Use Google here or request an SMS code on the signup page.',
      googleInitError: 'Google Sign-In could not initialize. Please refresh and try again.',
      googleMissingClientId: 'Google Sign-In client ID is not configured. Contact the administrator.',
      accountPlaceholder: 'Account / email / phone',
      accountInvalid: 'Enter a valid account identifier.',
      accountRequired: 'Account identifier is required.',
      passwordRequired: 'Password is required.',
      passwordTooShort: 'Password must be at least 8 characters long.',
      registerTitle: 'Create an account',
      confirmPasswordPlaceholder: 'Confirm password',
      registering: 'Creating account...',
      haveAccount: 'Already have an account? Log in',
      smsSendCode: 'Send code',
      smsResendIn: 'Resend in {{seconds}}s',
      smsResend: 'Resend code',
      smsCodeSent: 'Verification code sent. Please check your phone.',
      smsCodeFailed: 'Failed to send the verification code. Try again shortly.',
      smsRegisterTitle: 'Sign up with SMS',
      smsRegisterDescription: 'Only mainland China phone numbers are supported; we add +86 automatically when no country code is provided.',
      smsRegisterSuccess: 'Registration successful. Redirecting...',
      smsRegisterFailed: 'SMS registration failed. Please try again.',
      smsAutoCountryHint: '11-digit Chinese mobile numbers automatically prepend +86.',
      smsInvalidPhone: 'Only +86 phone numbers are supported at this time.',
      smsMissingFields: 'Phone number and verification code are required.',
    },
    chat: {
      guide: 'Guide',
      feedbase: 'Feedbase Management',
      admin: 'Admin',
      newConversation: 'New conversation',
      selectPrompt: 'Select or create a conversation',
      localeToggleLabel: 'Interface language',
      tokenUsageLabel: 'Tokens used',
      inputPlaceholder: 'Type your message...',
      thinking: 'Thinking...',
      thinkingStopped: 'Thinking (Stopped)',
      responding: 'Responding...',
      tierLabel: 'Plan',
      tierBadges: {
        free: 'Free',
        paid: 'Pro',
      },
      freeTierSessionHint: 'Free plan supports only cat & dog conversations and allows one active session at a time, with a 50,000-token limit per session.',
      promptLimitTitle: 'Session limit reached',
      promptLimitBody: 'This conversation exceeded the 50,000-token limit for the free plan. Start a new chat or upgrade your plan to continue.',
      promptLimitCTA: 'Explore upgrade options',
      promptLimitDismiss: 'Maybe later',
      askedQuestions: 'Asked',
      userResponse: 'Your Response',
      userInputPrefix: 'Reply to Inquiry',
    },
    planUpgrade: {
      title: 'Choose Your Plan',
      subtitle: 'Unlock more features and enhance your experience',
      comingSoon: 'Coming Soon',
      free: {
        name: 'Free',
        price: '$0',
        period: 'Forever free',
        features: [
          'System feedbase only',
          '1 session at a time',
          '50,000 tokens context limit',
          'Cat & dog types only',
        ],
      },
      pro: {
        name: 'Professional',
        price: 'TBD',
        period: 'Monthly subscription',
        features: [
          'Custom feedbase creation',
          'Unlimited sessions',
          '100,000 tokens context limit',
          'Real veterinarian service (with potential additional fee)',
          'Multimodal questions (disease pre-identification)',
          'Monthly message limit',
        ],
      },
      enterprise: {
        name: 'Enterprise',
        price: 'Contact Sales',
        period: 'Custom pricing',
        features: [
          'All livestock types (dairy, beef, etc.)',
          'Commercial nutrition model integration',
          'Agent customization',
          'Pay by usage',
          'Dedicated technical support',
          'Enterprise-grade SLA',
        ],
      },
    },
    sidebar: {
      title: 'Conversations',
      newChat: 'New chat',
      deleteAll: 'Clear',
      deleteConfirm: 'Delete this conversation?',
      deleteDescription: 'This action cannot be undone. This will permanently delete this conversation.',
      deleteAllConfirm: 'Delete all conversations? This cannot be undone.',
      deleteAllDescription: 'This action cannot be undone. This will permanently delete all your conversations.',
    },
    fileUpload: {
      uploading: 'Uploading...',
      attachFile: 'Attach File',
      removeFile: 'Remove File',
      fileUploaded: 'File Upload',
      filesCount: '{{count}} file(s)',
      fileTypesHint: '.txt, .py, .js, .json, .csv, .md, .html, .css, .xml, .yaml, .xlsx (Max 10MB)',
    },
    animalTypes: {
      selectTitle: 'Choose animal type',
      loading: 'Loading...',
      create: 'Create chat',
      dairy_cow: 'Dairy Cow',
      beef_cow: 'Beef Cow',
      cat: 'Cat',
      dog: 'Dog',
    },
    feedbases: {
      title: 'Feedbase Management',
      back: 'Back to chat',
      freeTierNotice: 'Free plan can only use system feedbases. Upgrade to create and edit custom libraries.',
    },
    guide: {
      back: 'Back to chat',
    },
    admin: {
      back: 'Back to chat',
      userManagement: 'User Management',
      feedbackManagement: 'Feedback Management',
      feedbackTitle: 'Feedback Management',
      unknownUser: 'Unknown User',
      viewSession: 'View Session',
      sessionHistory: 'Session History',
      noFeedbacks: 'No feedbacks found',
      sessionId: 'Session ID: {{id}}',
      errorFetch: 'Failed to fetch feedbacks',
      errorNetwork: 'Network error fetching feedbacks',
      close: 'Close',
    },
    protectedRoute: {
      deniedTitle: 'Access denied',
      deniedDescription: 'You do not have permission to view this page.',
    },
    register: {
      success: 'Registration successful. Please log in.',
      passwordMismatch: 'Passwords do not match',
    },
    errors: {
      networkRetry: 'Multiple retries failed. Check your network or refresh the page.',
      downloadFailed: 'Download failed: HTTP {{code}}',
    },
    feedback: {
      buttonLabel: 'Feedback',
      dialogTitle: 'Submit Feedback',
      dialogDescription: 'Help us improve by providing feedback on this session.',
      placeholder: 'Type your feedback here...',
      submit: 'Submit',
      success: 'Feedback submitted successfully',
      error: 'Failed to submit feedback',
    },
    artifact: {
      viewDynamicContent: '✨ View Dynamic Content',
      htmlDynamicContent: 'HTML Dynamic Content',
      viewSuggestion: '💡 View Suggestion',
      defaultTitle: 'HTML Artifact',
      recipeSuggestionPrefix: 'Suggestion - ',
      recipeAnalysisTitle: 'AI Nutritionist Analysis & Suggestion',
      suggestionTitle: '💡 Recipe Suggestion',
    },
    fileExport: {
      downloadRecipe: '✨ Download Report',
      format: '{{type}} Format',
      readyDownload: 'Ready to Download',
      recipeSuggestion: 'Recipe Suggestion',
    },
  },
}

type TranslationValue = string | TranslationTree

export function translate(locale: Locale, key: string): string | undefined {
  const parts = key.split('.')
  let current: TranslationValue | undefined = translations[locale]
  for (const part of parts) {
    if (typeof current === 'object' && current !== null && part in current) {
      const nextValue = current[part]
      current = nextValue as TranslationValue
    } else {
      return undefined
    }
  }
  return typeof current === 'string' ? current : undefined
}

export function getRawTranslation(locale: Locale, key: string): string | string[] | undefined {
  const parts = key.split('.')
  let current: string | string[] | TranslationTree | undefined = translations[locale]
  for (const part of parts) {
    if (typeof current === 'object' && current !== null && !Array.isArray(current) && part in current) {
      current = current[part]
    } else {
      return undefined
    }
  }
  if (typeof current === 'string' || Array.isArray(current)) {
    return current
  }
  return undefined
}

export function formatTranslation(locale: Locale, key: string, params?: Record<string, string | number>) {
  const value = translate(locale, key)
  if (!value) {
    return key
  }
  if (!params) {
    return value
  }
  return Object.entries(params).reduce((acc, [placeholder, replacement]) => {
    return acc.replaceAll(`{{${placeholder}}}`, String(replacement))
  }, value)
}

export function getLocaleName(target: Locale, displayLocale: Locale = 'zh-CN') {
  const localeNode = translations[displayLocale]
  if (
    typeof localeNode === 'object' &&
    localeNode !== null &&
    'common' in localeNode &&
    typeof localeNode.common === 'object' &&
    localeNode.common !== null &&
    'localeNames' in localeNode.common &&
    typeof localeNode.common.localeNames === 'object'
  ) {
    const labels = localeNode.common.localeNames as Record<string, string>
    return labels[target] || target
  }
  return target
}

export function normalizeLocale(value?: string | null): Locale {
  if (!value) {
    return defaultLocale
  }
  const normalized = value.trim().toLowerCase()
  if (normalized.startsWith('en')) {
    return 'en-US'
  }
  if (normalized.startsWith('zh')) {
    return 'zh-CN'
  }
  return defaultLocale
}

export function detectLocaleFromHeader(acceptLanguage?: string | null): Locale | undefined {
  if (!acceptLanguage) {
    return undefined
  }
  const [first] = acceptLanguage.split(',')
  if (!first) {
    return undefined
  }
  const locale = normalizeLocale(first)
  return supportedLocales.includes(locale) ? locale : undefined
}
