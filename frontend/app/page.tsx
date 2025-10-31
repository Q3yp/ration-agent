'use client'

import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Sparkles, Brain, Database, TrendingUp, ChevronRight, CheckCircle2 } from 'lucide-react'

export default function LandingPage() {
  const router = useRouter()

  const handleGetStarted = () => {
    router.push('/login')
  }

  const handleGoToChat = () => {
    router.push('/chat')
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      {/* Navigation */}
      <nav className="border-b bg-white/80 backdrop-blur-sm fixed w-full top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex justify-between items-center">
          <div className="flex items-center gap-2">
            <Sparkles className="h-6 w-6 text-primary" />
            <span className="text-xl font-bold bg-gradient-to-r from-primary to-primary/70 bg-clip-text text-transparent">
              辉途智能配方助手
            </span>
          </div>
          <div className="flex gap-2">
            <Button onClick={handleGoToChat} variant="outline">
              进入应用
            </Button>
            <Button onClick={handleGetStarted} variant="default">
              登录
            </Button>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="pt-32 pb-20 px-6">
        <div className="max-w-7xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 bg-primary/10 text-primary px-4 py-2 rounded-full mb-6">
            <Sparkles className="h-4 w-4" />
            <span className="text-sm font-medium">AI 驱动的智能营养配方平台</span>
          </div>

          <h1 className="text-5xl md:text-6xl font-bold mb-6 bg-gradient-to-r from-gray-900 via-gray-800 to-gray-700 bg-clip-text text-transparent">
            让专业配方设计，像聊天一样简单
          </h1>

          <p className="text-xl text-gray-600 mb-8 max-w-3xl mx-auto">
            无需复杂计算，只需自然对话<br/>
            AI 助手帮您完成从需求分析到配方优化的全过程
          </p>

          <div className="flex gap-4 justify-center">
            <Button size="lg" onClick={handleGetStarted} className="group">
              开始使用
              <ChevronRight className="ml-2 h-4 w-4 group-hover:translate-x-1 transition-transform" />
            </Button>
          </div>

          {/* Use Cases */}
          <div className="mt-16 grid md:grid-cols-2 gap-6 max-w-4xl mx-auto text-left">
            <div className="bg-white rounded-xl p-6 shadow-md border-2 border-primary/20">
              <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
                <span className="text-2xl">🏢</span>
                企业级畜牧方案
              </h3>
              <p className="text-gray-600 text-sm mb-3">
                为牧场、养殖企业提供专业配方设计
              </p>
              <div className="flex gap-2">
                <span className="bg-primary/10 text-primary text-xs px-3 py-1 rounded-full">🐄 奶牛</span>
                <span className="bg-primary/10 text-primary text-xs px-3 py-1 rounded-full">🐂 肉牛</span>
              </div>
            </div>

            <div className="bg-white rounded-xl p-6 shadow-md border-2 border-blue-200">
              <h3 className="text-lg font-semibold mb-3 flex items-center gap-2">
                <span className="text-2xl">🏠</span>
                个人宠物营养
              </h3>
              <p className="text-gray-600 text-sm mb-3">
                为宠物主人提供科学喂养建议
              </p>
              <div className="flex gap-2">
                <span className="bg-blue-100 text-blue-700 text-xs px-3 py-1 rounded-full">🐱 猫</span>
                <span className="bg-blue-100 text-blue-700 text-xs px-3 py-1 rounded-full">🐶 狗</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section className="py-20 px-6 bg-white">
        <div className="max-w-7xl mx-auto">
          <h2 className="text-3xl md:text-4xl font-bold text-center mb-4">
            为什么选择辉途
          </h2>
          <p className="text-center text-gray-600 mb-12 max-w-2xl mx-auto">
            告别繁琐的手工计算和复杂的软件操作，用对话就能完成专业配方设计
          </p>

          <div className="grid md:grid-cols-3 gap-8">
            <Card className="border-2 hover:border-primary/50 transition-colors">
              <CardContent className="pt-6">
                <div className="h-12 w-12 bg-primary/10 rounded-lg flex items-center justify-center mb-4">
                  <Brain className="h-6 w-6 text-primary" />
                </div>
                <h3 className="text-xl font-semibold mb-2">自然语言交互</h3>
                <p className="text-gray-600">
                  用日常语言描述需求，AI 助手自动理解并执行。无需学习复杂操作，像聊天一样完成配方设计
                </p>
              </CardContent>
            </Card>

            <Card className="border-2 hover:border-primary/50 transition-colors">
              <CardContent className="pt-6">
                <div className="h-12 w-12 bg-primary/10 rounded-lg flex items-center justify-center mb-4">
                  <Database className="h-6 w-6 text-primary" />
                </div>
                <h3 className="text-xl font-semibold mb-2">专业知识库支持</h3>
                <p className="text-gray-600">
                  内置国际营养标准（NRC、FEDIAF），支持自定义饲料库，数据可导入导出，随时调用
                </p>
              </CardContent>
            </Card>

            <Card className="border-2 hover:border-primary/50 transition-colors">
              <CardContent className="pt-6">
                <div className="h-12 w-12 bg-primary/10 rounded-lg flex items-center justify-center mb-4">
                  <TrendingUp className="h-6 w-6 text-primary" />
                </div>
                <h3 className="text-xl font-semibold mb-2">全流程自动化</h3>
                <p className="text-gray-600">
                  从需求分析、资料查询、配方计算到报告生成，AI 自动完成，您只需审核结果
                </p>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="py-20 px-6 bg-gray-50">
        <div className="max-w-7xl mx-auto">
          <h2 className="text-3xl md:text-4xl font-bold text-center mb-4">
            如何使用
          </h2>
          <p className="text-center text-gray-600 mb-12 max-w-2xl mx-auto">
            三步完成专业配方设计，AI 帮您处理所有复杂的技术细节
          </p>

          <div className="grid md:grid-cols-3 gap-8">
            <div className="text-center">
              <div className="w-16 h-16 bg-primary text-white rounded-full flex items-center justify-center text-2xl font-bold mx-auto mb-4">
                1
              </div>
              <h3 className="text-xl font-semibold mb-2">描述需求</h3>
              <p className="text-gray-600">
                告诉 AI 您的配方目标，比如&ldquo;设计一个高产奶牛配方&rdquo;或&ldquo;我家猫需要减肥食谱&rdquo;
              </p>
            </div>

            <div className="text-center">
              <div className="w-16 h-16 bg-primary text-white rounded-full flex items-center justify-center text-2xl font-bold mx-auto mb-4">
                2
              </div>
              <h3 className="text-xl font-semibold mb-2">AI 自动处理</h3>
              <p className="text-gray-600">
                系统自动查询营养标准、调用饲料库、执行配方计算，全程无需您手动操作
              </p>
            </div>

            <div className="text-center">
              <div className="w-16 h-16 bg-primary text-white rounded-full flex items-center justify-center text-2xl font-bold mx-auto mb-4">
                3
              </div>
              <h3 className="text-xl font-semibold mb-2">获取结果</h3>
              <p className="text-gray-600">
                收到完整配方方案和营养分析报告，可直接导出使用或继续优化调整
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Use Cases Detail */}
      <section className="py-20 px-6">
        <div className="max-w-7xl mx-auto">
          <h2 className="text-3xl md:text-4xl font-bold text-center mb-12">
            适用场景
          </h2>

          <div className="grid md:grid-cols-2 gap-8">
            {/* Corporate */}
            <Card className="border-2 border-primary/30">
              <CardContent className="p-8">
                <div className="flex items-center gap-3 mb-4">
                  <span className="text-4xl">🏢</span>
                  <h3 className="text-2xl font-bold">企业级畜牧方案</h3>
                </div>
                <p className="text-gray-600 mb-4">
                  为奶牛场、肉牛养殖企业提供专业营养配方设计与优化服务
                </p>
                <div className="space-y-3">
                  {[
                    '🐄 奶牛配方：基于 NRC 2021 标准，优化产奶量与乳成分',
                    '🐂 肉牛配方：科学能量配比，提升日增重与胴体品质',
                    '📊 Excel 数据支持：导入现有饲料库与配方数据',
                    '💰 成本优化：在满足营养需求的前提下降低饲料成本'
                  ].map((item, i) => (
                    <div key={i} className="flex items-start gap-2">
                      <CheckCircle2 className="h-5 w-5 text-primary flex-shrink-0 mt-0.5" />
                      <span className="text-sm text-gray-700">{item}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            {/* Individual */}
            <Card className="border-2 border-blue-300">
              <CardContent className="p-8">
                <div className="flex items-center gap-3 mb-4">
                  <span className="text-4xl">🏠</span>
                  <h3 className="text-2xl font-bold">个人宠物营养</h3>
                </div>
                <p className="text-gray-600 mb-4">
                  为宠物主人提供科学、专业的猫狗营养配方建议
                </p>
                <div className="space-y-3">
                  {[
                    '🐱 猫营养：符合专性肉食动物需求，确保牛磺酸等关键营养',
                    '🐶 狗营养：根据生命阶段（幼年/成年/老年）定制配方',
                    '⚖️ 体重管理：减肥、增重、维持体重的专业建议',
                    '🏥 特殊需求：过敏、疾病等特殊情况的营养方案'
                  ].map((item, i) => (
                    <div key={i} className="flex items-start gap-2">
                      <CheckCircle2 className="h-5 w-5 text-blue-600 flex-shrink-0 mt-0.5" />
                      <span className="text-sm text-gray-700">{item}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="py-20 px-6 bg-gradient-to-r from-primary to-primary/80">
        <div className="max-w-4xl mx-auto text-center text-white">
          <h2 className="text-3xl md:text-4xl font-bold mb-4">
            开始您的智能配方之旅
          </h2>
          <p className="text-xl mb-8 opacity-90">
            无论您是养殖企业还是宠物主人，让 AI 助手帮您做出更科学的营养决策
          </p>
          <Button
            size="lg"
            onClick={handleGetStarted}
            variant="secondary"
            className="group"
          >
            立即体验
            <ChevronRight className="ml-2 h-4 w-4 group-hover:translate-x-1 transition-transform" />
          </Button>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 px-6 bg-gray-900 text-gray-400 text-center">
        <p className="text-sm">
          © 2025 辉途智能配方助手 · 让专业配方设计更简单
        </p>
      </footer>
    </div>
  )
}
