export type Locale = 'zh-CN' | 'en-US'

export const supportedLocales: Locale[] = ['zh-CN', 'en-US']
export const defaultLocale: Locale = 'zh-CN'

interface TranslationTree {
  [key: string]: string | TranslationTree
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
      heroBadge: 'AI 驱动的智能营养配方平台',
      heroTitle: '让专业配方设计，像聊天一样简单',
      heroSubtitle: '无需复杂计算，只需自然对话\nAI 助手帮您完成从需求分析到配方优化的全过程',
      useCases: {
        enterpriseTitle: '企业级畜牧方案',
        enterpriseDescription: '为牧场、养殖企业提供专业配方设计',
        enterpriseTags: '🐄 奶牛, 🐂 肉牛',
        personalTitle: '个人宠物营养',
        personalDescription: '为宠物主人提供科学喂养建议',
        personalTags: '🐱 猫, 🐶 狗',
      },
      featuresTitle: '为什么选择辉途',
      featuresSubtitle: '告别繁琐的手工计算和复杂的软件操作，用对话就能完成专业配方设计',
      featureNaturalTitle: '自然语言交互',
      featureNaturalDescription: '用日常语言描述需求，AI 助手自动理解并执行。无需学习复杂操作，像聊天一样完成配方设计',
      featureKnowledgeTitle: '专业知识库支持',
      featureKnowledgeDescription: '内置国际营养标准（NRC、FEDIAF），支持自定义饲料库，数据可导入导出，随时调用',
      featureAutomationTitle: '全流程自动化',
      featureAutomationDescription: '从需求分析、资料查询、配方计算到报告生成，AI 自动完成，您只需审核结果',
      howItWorksTitle: '如何使用',
      howItWorksSubtitle: '三步完成专业配方设计，AI 帮您处理所有复杂的技术细节',
      stepDescribeTitle: '描述需求',
      stepDescribeDescription: '告诉 AI 您的配方目标，比如“设计一个高产奶牛配方”或“我家猫需要减肥食谱”',
      stepProcessTitle: 'AI 自动处理',
      stepProcessDescription: '系统自动查询营养标准、调用饲料库、执行配方计算，全程无需您手动操作',
      stepResultTitle: '获取结果',
      stepResultDescription: '收到完整配方方案和营养分析报告，可直接导出使用或继续优化调整',
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
    },
    sidebar: {
      title: '对话列表',
      newChat: '新建对话',
      deleteAll: '清空',
      deleteConfirm: '您确定要删除这个对话吗？',
      deleteAllConfirm: '您确定要删除所有对话吗？这个操作不可恢复。',
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
    },
    guide: {
      back: '返回对话',
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
  },
  'en-US': {
    common: {
      appName: 'Huitu Nutrition Copilot',
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
      heroBadge: 'AI-powered nutrition formulation platform',
      heroTitle: 'Professional formulations that feel like a conversation',
      heroSubtitle: 'Skip spreadsheets—describe your goal and let the AI handle analysis, optimization, and reporting.',
      useCases: {
        enterpriseTitle: 'Enterprise livestock solutions',
        enterpriseDescription: 'Precision formulations for farms and feed companies',
        enterpriseTags: '🐄 Dairy, 🐂 Beef',
        personalTitle: 'Pet nutrition coaching',
        personalDescription: 'Science-based feeding plans for pet owners',
        personalTags: '🐱 Cats, 🐶 Dogs',
      },
      featuresTitle: 'Why choose Huitu',
      featuresSubtitle: 'Replace manual calculations with conversational workflows.',
      featureNaturalTitle: 'Natural-language workflow',
      featureNaturalDescription: 'Describe objectives in everyday language and let the AI execute the steps.',
      featureKnowledgeTitle: 'Built-in standards & feedbases',
      featureKnowledgeDescription: 'NRC/FEDIAF guidelines plus custom feed libraries with import/export.',
      featureAutomationTitle: 'End-to-end automation',
      featureAutomationDescription: 'Requirement analysis, optimizer runs, and report generation handled for you.',
      howItWorksTitle: 'How it works',
      howItWorksSubtitle: 'Three guided steps to a validated formulation.',
      stepDescribeTitle: 'Describe the goal',
      stepDescribeDescription: 'Explain what you need, e.g., “High-yield dairy ration” or “Weight-control plan for my cat.”',
      stepProcessTitle: 'AI handles the work',
      stepProcessDescription: 'We gather standards, pull feed data, and run the optimizer—no manual juggling.',
      stepResultTitle: 'Review the result',
      stepResultDescription: 'Receive a full formulation and nutrient analysis ready for export or iteration.',
    },
    auth: {
      loginTitle: 'Log in to Huitu Nutrition Copilot',
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
      feedbase: 'Feedbase Manager',
      admin: 'Admin',
      newConversation: 'New Conversation',
      selectPrompt: 'Select or create a conversation',
      localeToggleLabel: 'Interface language',
      tokenUsageLabel: 'Tokens used',
      inputPlaceholder: 'Type your message...',
    },
    sidebar: {
      title: 'Conversations',
      newChat: 'New chat',
      deleteAll: 'Clear',
      deleteConfirm: 'Delete this conversation?',
      deleteAllConfirm: 'Delete all conversations? This cannot be undone.',
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
      title: 'Feedbase Manager',
      back: 'Back to chat',
    },
    guide: {
      back: 'Back to chat',
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
