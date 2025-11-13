import { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import './App.css'

// Viteのプロキシ設定により、相対パスでアクセス
const API_BASE_URL = ''

interface Message {
  role: 'user' | 'assistant'
  content: string
}

interface ChatEvent {
  type: 'content' | 'tool_use' | 'step_update' | 'done' | 'error' | 'status'
  data?: string
  tool?: string
  show_modal?: boolean
  step?: string
  confidence?: string
  reasoning?: string
  content?: string
  error?: string
  status?: 'thinking' | 'tool_use' | 'none'
  message?: string
}

interface UserInfo {
  industry?: string
  products?: string
  companySize?: string
  region?: string
  clientIndustry?: string
  priceTransferStatus?: string
}

interface CostAnalysisData {
  before_sales: string
  before_cost: string
  before_expenses: string
  current_sales: string
  current_cost: string
  current_expenses: string
}

// ステップ名をユーザー向けに変換
function formatStepName(step: string): string {
  const stepMap: { [key: string]: string } = {
    'STEP_0_CHECK_1': '価格交渉準備編 - 取引条件・業務内容の確認',
    'STEP_0_CHECK_2': '価格交渉準備編 - 原材料費・労務費データの定期収集',
    'STEP_0_CHECK_3': '価格交渉準備編 - 原価計算の実施',
    'STEP_0_CHECK_4': '価格交渉準備編 - 単価表の作成',
    'STEP_0_CHECK_5': '価格交渉準備編 - 見積書フォーマットの整備',
    'STEP_0_CHECK_6': '価格交渉準備編 - 取引先の経営方針・業績把握',
    'STEP_0_CHECK_7': '価格交渉準備編 - 自社の付加価値の明確化',
    'STEP_0_CHECK_8': '価格交渉準備編 - 適正な取引慣行の確認',
    'STEP_0_CHECK_9': '価格交渉準備編 - 価格転嫁の必要性判定',
    'STEP_1': '価格交渉実践編 - 業界動向の情報収集',
    'STEP_2': '価格交渉実践編 - 取引先情報収集と交渉方針検討',
    'STEP_3': '価格交渉実践編 - 書面での申し入れ',
    'STEP_4': '価格交渉実践編 - 説明資料の準備',
    'STEP_5': '価格交渉実践編 - 発注後に発生する価格交渉',
  }
  return stepMap[step] || step
}

function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [currentStep, setCurrentStep] = useState<string | null>(null)
  const [latestDiagram, setLatestDiagram] = useState<string | null>(null)
  const [diagramMessageIndex, setDiagramMessageIndex] = useState<number | null>(null) // 図が紐づくメッセージのインデックス
  const [showUserInfoModal, setShowUserInfoModal] = useState(true)
  const [userInfo, setUserInfo] = useState<UserInfo>({})
  const [showCostAnalysisModal, setShowCostAnalysisModal] = useState(false)
  const [costAnalysisData, setCostAnalysisData] = useState<CostAnalysisData>({
    before_sales: '',
    before_cost: '',
    before_expenses: '',
    current_sales: '',
    current_cost: '',
    current_expenses: ''
  })
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [currentStatus, setCurrentStatus] = useState<string>('') // 現在のステータスメッセージ
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const currentResponseRef = useRef<string>('')
  const abortControllerRef = useRef<AbortController | null>(null)
  const previousDiagramUrlRef = useRef<string | null>(null)

  // セッション初期化（ユーザー情報入力後）
  const initSession = async (userInfo: UserInfo) => {
    try {
      // 図をクリア
      setLatestDiagram(null)
      setDiagramMessageIndex(null)
      previousDiagramUrlRef.current = null
      
      const response = await axios.post(`${API_BASE_URL}/api/session`, { user_info: userInfo })
      setSessionId(response.data.session_id)
      
      // ウェルカムメッセージ（ユーザー情報に基づいてカスタマイズ）
      let welcomeContent = `こんにちは！価格転嫁支援AIアシスタントです。

皆様の価格転嫁をサポートさせていただきます。`

      if (userInfo.industry || userInfo.products) {
        welcomeContent += `\n\n`
        if (userInfo.industry) {
          welcomeContent += `**業種**: ${userInfo.industry}\n`
        }
        if (userInfo.products) {
          welcomeContent += `**主な製品・サービス**: ${userInfo.products}\n`
        }
        if (userInfo.region) {
          welcomeContent += `**地域**: ${userInfo.region}\n`
        }
        welcomeContent += `\n上記の情報を踏まえて、より具体的なアドバイスを提供させていただきます。`
      }

      welcomeContent += `

**できること:**
価格転嫁プロセス（準備編・実践編）の各ステップについてアドバイス
原価計算や見積書作成などの具体的な手順の説明
業界動向や事例の検索
データの可視化（グラフ作成）

**使い方:**
お困りのことや知りたいことを、お気軽にご質問ください。
例: 「原価計算のやり方を教えて」「見積書の作り方は？」「業界の価格転嫁動向を知りたい」

どのようなことでお手伝いできますか？`

      const welcomeMessage: Message = {
        role: 'assistant',
        content: welcomeContent
      }
      setMessages([welcomeMessage])
    } catch (error) {
      console.error('セッション初期化エラー:', error)
    }
  }

  // ユーザー情報送信ハンドラ
  const handleUserInfoSubmit = () => {
    setShowUserInfoModal(false)
    initSession(userInfo)
  }

  // 最新の図を取得（セッションに紐づく）
  useEffect(() => {
    if (!sessionId) {
      setLatestDiagram(null)
      setDiagramMessageIndex(null)
      previousDiagramUrlRef.current = null
      return
    }

    const fetchLatestDiagram = async () => {
      try {
        const response = await axios.get(`${API_BASE_URL}/api/diagrams/latest`, {
          params: { session_id: sessionId }
        })
        if (response.data.diagram) {
          // URLを直接使用
          const newDiagramUrl = response.data.diagram.url
          
          // 図が新しく生成された場合（URLが変わった場合）
          if (newDiagramUrl !== previousDiagramUrlRef.current) {
            previousDiagramUrlRef.current = newDiagramUrl
            // diagramMessageIndexは別のuseEffectで更新
          }
          
          setLatestDiagram(newDiagramUrl)
        } else {
          setLatestDiagram(null)
          setDiagramMessageIndex(null)
          previousDiagramUrlRef.current = null
        }
      } catch (error) {
        console.error('図の取得エラー:', error)
      }
    }
    
    fetchLatestDiagram() // 初回取得
    const interval = setInterval(fetchLatestDiagram, 2000) // 2秒ごとにチェック
    return () => clearInterval(interval)
  }, [sessionId])
  
  // 図が新しく生成されたとき、またはメッセージが更新されたときに、図が紐づくメッセージインデックスを更新
  useEffect(() => {
    // 図が存在し、メッセージがある場合
    if (latestDiagram && messages.length > 0) {
      // 図が新しく生成された場合（previousDiagramUrlRefと異なる場合）、インデックスを更新
      const isNewDiagram = latestDiagram !== previousDiagramUrlRef.current
      
      if (isNewDiagram || diagramMessageIndex === null) {
        // 最後のアシスタントメッセージのインデックスを探す
        for (let i = messages.length - 1; i >= 0; i--) {
          if (messages[i].role === 'assistant') {
            setDiagramMessageIndex(i)
            break
          }
        }
      }
    } else if (!latestDiagram) {
      // 図がなくなった場合はインデックスもクリア
      setDiagramMessageIndex(null)
    }
  }, [messages, latestDiagram, diagramMessageIndex])

  // メッセージが更新されたらスクロール
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
      setIsLoading(false)
      
      // 停止メッセージを追加
      if (currentResponseRef.current) {
        setMessages(prev => {
          const newMessages = [...prev]
          if (newMessages.length > 0 && newMessages[newMessages.length - 1].role === 'assistant') {
            newMessages[newMessages.length - 1] = {
              role: 'assistant',
              content: currentResponseRef.current + '\n\n*[応答が停止されました]*',
            }
          }
          return newMessages
        })
      }
    }
  }

  const handleSend = async (messageOverride?: string, skipUserMessage: boolean = false) => {
    const messageToSend = messageOverride || input
    if (!messageToSend.trim() || !sessionId || isLoading) return

    // ユーザーメッセージを追加（skipUserMessageがtrueの場合はスキップ）
    if (!skipUserMessage) {
      const userMessage: Message = { role: 'user', content: messageToSend }
      setMessages(prev => [...prev, userMessage])
    }
    
    if (!messageOverride) {
      setInput('')
    }
    setIsLoading(true)
    currentResponseRef.current = ''

    // AbortControllerを作成
    abortControllerRef.current = new AbortController()

    try {
      const response = await fetch(`${API_BASE_URL}/api/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: messageToSend,
          session_id: sessionId,
        }),
        signal: abortControllerRef.current.signal,
      })

      if (!response.ok) {
        throw new Error('レスポンスエラー')
      }

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()

      if (!reader) {
        throw new Error('ストリームが取得できませんでした')
      }

      // アシスタントメッセージを追加（最初のcontentイベントで更新される）
      let hasAddedAssistantMessage = false

      try {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          const chunk = decoder.decode(value)
          const lines = chunk.split('\n')

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const event: ChatEvent = JSON.parse(line.slice(6))

                if (event.type === 'content') {
                  currentResponseRef.current = event.data || ''
                  
                  // 最初のcontentイベントでアシスタントメッセージを追加
                  if (!hasAddedAssistantMessage) {
                    hasAddedAssistantMessage = true
                    setMessages(prev => [...prev, { role: 'assistant', content: currentResponseRef.current }])
                  } else {
                    // 既存のメッセージを更新
                    setMessages(prev => {
                      const newMessages = [...prev]
                      newMessages[newMessages.length - 1] = {
                        role: 'assistant',
                        content: currentResponseRef.current,
                      }
                      return newMessages
                    })
                  }
                } else if (event.type === 'status') {
                  // ステータス更新（思考中、検索中など）
                  if (event.status === 'none') {
                    setCurrentStatus('')
                  } else {
                    setCurrentStatus(event.message || '')
                  }
                } else if (event.type === 'tool_use') {
                  // ツール使用中
                  console.log(`[ツール使用中] ${event.tool}`)
                  
                  // analyze_cost_impactツールの場合はモーダルを表示
                  if (event.tool === 'analyze_cost_impact' && event.show_modal) {
                    setShowCostAnalysisModal(true)
                  }
                } else if (event.type === 'step_update') {
                  setCurrentStep(event.step || null)
                  // ステップ更新通知をメッセージに追加（ユーザー向けに分かりやすく）
                  const formattedStep = formatStepName(event.step || '')
                  const stepMessage = `\n\n**📌 現在のステップ: ${formattedStep}**\n\n`
                  currentResponseRef.current += stepMessage
                  
                  // アシスタントメッセージがまだ追加されていない場合は追加
                  if (!hasAddedAssistantMessage) {
                    hasAddedAssistantMessage = true
                    setMessages(prev => [...prev, { role: 'assistant', content: currentResponseRef.current }])
                  } else {
                    setMessages(prev => {
                      const newMessages = [...prev]
                      newMessages[newMessages.length - 1] = {
                        role: 'assistant',
                        content: currentResponseRef.current,
                      }
                      return newMessages
                    })
                  }
                } else if (event.type === 'done') {
                  // ステータスをクリア
                  setCurrentStatus('')
                  
                  // アシスタントメッセージがまだ追加されていない場合は追加
                  if (!hasAddedAssistantMessage) {
                    hasAddedAssistantMessage = true
                    setMessages(prev => [...prev, { role: 'assistant', content: event.content || currentResponseRef.current }])
                  } else {
                    setMessages(prev => {
                      const newMessages = [...prev]
                      newMessages[newMessages.length - 1] = {
                        role: 'assistant',
                        content: event.content || currentResponseRef.current,
                      }
                      return newMessages
                    })
                  }
                } else if (event.type === 'error') {
                  // エラー時は必ずメッセージを追加
                  if (!hasAddedAssistantMessage) {
                    hasAddedAssistantMessage = true
                    setMessages(prev => [...prev, { role: 'assistant', content: `❌ エラー: ${event.error}` }])
                  } else {
                    setMessages(prev => {
                      const newMessages = [...prev]
                      newMessages[newMessages.length - 1] = {
                        role: 'assistant',
                        content: `❌ エラー: ${event.error}`,
                      }
                      return newMessages
                    })
                  }
                }
              } catch (e) {
                console.error('イベントパースエラー:', e)
              }
            }
          }
        }
      } catch (error: any) {
        // AbortErrorの場合は停止されたので、エラーを表示しない
        if (error.name === 'AbortError') {
          console.log('ストリーミングが停止されました')
          return
        }
        throw error
      }
    } catch (error: any) {
      // AbortErrorの場合は停止されたので、エラーを表示しない
      if (error.name === 'AbortError') {
        console.log('リクエストが停止されました')
        return
      }
      console.error('チャットエラー:', error)
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: `❌ エラーが発生しました: ${error}` },
      ])
    } finally {
      setIsLoading(false)
      setCurrentStatus('') // ローディング終了時にステータスをクリア
      abortControllerRef.current = null
    }
  }

  // 価格転嫁検討ツールの実行
  const handleCostAnalysisSubmit = async () => {
    setIsAnalyzing(true)
    try {
      // 数値に変換
      const data = {
        before_sales: parseFloat(costAnalysisData.before_sales) || 0,
        before_cost: parseFloat(costAnalysisData.before_cost) || 0,
        before_expenses: parseFloat(costAnalysisData.before_expenses) || 0,
        current_sales: parseFloat(costAnalysisData.current_sales) || 0,
        current_cost: parseFloat(costAnalysisData.current_cost) || 0,
        current_expenses: parseFloat(costAnalysisData.current_expenses) || 0
      }

      // バリデーション
      if (data.before_sales <= 0 || data.current_sales <= 0) {
        alert('売上高は0より大きい値を入力してください')
        setIsAnalyzing(false)
        return
      }

      const response = await axios.post(`${API_BASE_URL}/api/cost-analysis`, data)
      
      if (response.data.success) {
        const result = response.data.result
        
        // モーダルを閉じる
        setShowCostAnalysisModal(false)
        setCostAnalysisData({
          before_sales: '',
          before_cost: '',
          before_expenses: '',
          current_sales: '',
          current_cost: '',
          current_expenses: ''
        })
        
        // 分析結果をエージェントに送信して、要約と図示を依頼
        const analysisResultText = `【価格転嫁検討ツール - 分析結果】

【コスト高騰前の状況】
売上高: ${result.before.sales.toLocaleString()}円
売上原価: ${result.before.cost.toLocaleString()}円
販管費・その他経費: ${result.before.expenses.toLocaleString()}円
総コスト: ${result.before.total_cost.toLocaleString()}円
利益: ${result.before.profit.toLocaleString()}円
利益率: ${result.before.profit_rate.toFixed(2)}%

【現在の状況】
売上高: ${result.current.sales.toLocaleString()}円
売上原価: ${result.current.cost.toLocaleString()}円
販管費・その他経費: ${result.current.expenses.toLocaleString()}円
総コスト: ${result.current.total_cost.toLocaleString()}円
利益: ${result.current.profit.toLocaleString()}円
利益率: ${result.current.profit_rate.toFixed(2)}%

【コスト高騰の影響】
売上高: ${result.changes.sales.amount >= 0 ? '+' : ''}${result.changes.sales.amount.toLocaleString()}円 (${result.changes.sales.rate >= 0 ? '+' : ''}${result.changes.sales.rate.toFixed(2)}%)
売上原価: ${result.changes.cost.amount >= 0 ? '+' : ''}${result.changes.cost.amount.toLocaleString()}円 (${result.changes.cost.rate >= 0 ? '+' : ''}${result.changes.cost.rate.toFixed(2)}%)
販管費・その他経費: ${result.changes.expenses.amount >= 0 ? '+' : ''}${result.changes.expenses.amount.toLocaleString()}円 (${result.changes.expenses.rate >= 0 ? '+' : ''}${result.changes.expenses.rate.toFixed(2)}%)
総コスト: ${result.changes.total_cost.amount >= 0 ? '+' : ''}${result.changes.total_cost.amount.toLocaleString()}円 (${result.changes.total_cost.rate >= 0 ? '+' : ''}${result.changes.total_cost.rate.toFixed(2)}%)
利益: ${result.changes.profit.amount >= 0 ? '+' : ''}${result.changes.profit.amount.toLocaleString()}円 (${result.changes.profit.rate >= 0 ? '+' : ''}${result.changes.profit.rate.toFixed(2)}%)

【参考価格の算出】
コスト高騰前の利益率を維持するための参考価格: ${result.reference_price.toLocaleString()}円
現在の価格との差額: ${result.price_gap >= 0 ? '+' : ''}${result.price_gap.toLocaleString()}円 (${result.price_gap_rate >= 0 ? '+' : ''}${result.price_gap_rate.toFixed(2)}%)`

        // 図生成用のデータも含める
        const dataValues = [
          result.before.sales / 1000000,
          result.before.cost / 1000000,
          result.before.expenses / 1000000,
          result.before.total_cost / 1000000,
          result.before.profit / 1000000,
          result.current.sales / 1000000,
          result.current.cost / 1000000,
          result.current.expenses / 1000000,
          result.current.total_cost / 1000000,
          result.current.profit / 1000000,
        ]
        
        const labelsList = [
          "売上高(前)",
          "売上原価(前)",
          "販管費(前)",
          "総コスト(前)",
          "利益(前)",
          "売上高(現在)",
          "売上原価(現在)",
          "販管費(現在)",
          "総コスト(現在)",
          "利益(現在)"
        ]
        
        const diagramData = JSON.stringify({
          data: dataValues,
          labels: labelsList
        }, null, 2)
        
        // エージェントに要約と図示を依頼（内部処理として、画面には表示しない）
        const agentRequest = `価格転嫁検討ツールで分析しました。以下の分析結果を要約して、分かりやすく説明してください。また、このデータを使って generate_diagram ツールで棒グラフも生成してください。

${analysisResultText}

【図示用データ】
${diagramData}

このデータを使って、コスト高騰前と現在の売上高、売上原価、販管費、総コスト、利益を比較する棒グラフを作成してください。`
        
        // エージェントに送信（ユーザーメッセージは表示しない）
        setTimeout(() => {
          handleSend(agentRequest, true) // 第2引数でユーザーメッセージの表示をスキップ
        }, 300)
      } else {
        alert(`分析エラー: ${response.data.message}`)
      }
    } catch (error: any) {
      console.error('コスト分析エラー:', error)
      alert(`エラーが発生しました: ${error.response?.data?.message || error.message}`)
    } finally {
      setIsAnalyzing(false)
    }
  }

  const handleClear = async () => {
    if (!sessionId) return

    try {
      // 図を先にクリア
      setLatestDiagram(null)
      setDiagramMessageIndex(null)
      previousDiagramUrlRef.current = null
      
      await axios.post(`${API_BASE_URL}/api/session/${sessionId}/clear`)
      setMessages([])
      setCurrentStep(null)
      
      // ウェルカムメッセージを再表示
      const welcomeMessage: Message = {
        role: 'assistant',
        content: `こんにちは！価格転嫁支援AIアシスタントです。

皆様の価格転嫁をサポートさせていただきます。

**できること:**
価格転嫁プロセス（準備編・実践編）の各ステップについてアドバイス
原価計算や見積書作成などの具体的な手順の説明
業界動向や事例の検索
データの可視化（グラフ作成）

**使い方:**
お困りのことや知りたいことを、お気軽にご質問ください。
例: 「原価計算のやり方を教えて」「見積書の作り方は？」「業界の価格転嫁動向を知りたい」

どのようなことでお手伝いできますか？`
      }
      setMessages([welcomeMessage])
    } catch (error) {
      console.error('クリアエラー:', error)
    }
  }

  return (
    <div className="app">
      {/* ユーザー情報入力モーダル */}
      {showUserInfoModal && (
        <div className="modal-overlay">
          <div className="modal-content">
            <h2>基本情報の入力</h2>
            <p className="modal-description">
              より適切なアドバイスを提供するために、以下をご入力ください。<br />
              入力できる項目のみご記入いただき、「登録して開始」をクリックしてください。
            </p>
            
            <div className="form-group">
              <label htmlFor="industry">業種</label>
              <select
                id="industry"
                value={userInfo.industry || ''}
                onChange={(e) => setUserInfo({ ...userInfo, industry: e.target.value || undefined })}
                className="form-input"
              >
                <option value="">選択してください</option>
                <option value="製造業">製造業</option>
                <option value="建設業">建設業</option>
                <option value="小売業">小売業</option>
                <option value="サービス業">サービス業</option>
                <option value="卸売業">卸売業</option>
                <option value="運輸業">運輸業</option>
                <option value="飲食業">飲食業</option>
                <option value="IT・情報通信業">IT・情報通信業</option>
                <option value="その他">その他</option>
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="products">主な製品・サービス</label>
              <input
                id="products"
                type="text"
                value={userInfo.products || ''}
                onChange={(e) => setUserInfo({ ...userInfo, products: e.target.value || undefined })}
                placeholder="例: 金属加工部品、Web制作サービスなど"
                className="form-input"
              />
            </div>

            <div className="form-group">
              <label htmlFor="companySize">従業員規模</label>
              <select
                id="companySize"
                value={userInfo.companySize || ''}
                onChange={(e) => setUserInfo({ ...userInfo, companySize: e.target.value || undefined })}
                className="form-input"
              >
                <option value="">選択してください</option>
                <option value="1-5人">1-5人</option>
                <option value="6-20人">6-20人</option>
                <option value="21-50人">21-50人</option>
                <option value="51-100人">51-100人</option>
                <option value="101-300人">101-300人</option>
                <option value="300人以上">300人以上</option>
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="region">地域（都道府県）</label>
              <select
                id="region"
                value={userInfo.region || ''}
                onChange={(e) => setUserInfo({ ...userInfo, region: e.target.value || undefined })}
                className="form-input"
              >
                <option value="">選択してください</option>
                <option value="北海道">北海道</option>
                <option value="青森県">青森県</option>
                <option value="岩手県">岩手県</option>
                <option value="宮城県">宮城県</option>
                <option value="秋田県">秋田県</option>
                <option value="山形県">山形県</option>
                <option value="福島県">福島県</option>
                <option value="茨城県">茨城県</option>
                <option value="栃木県">栃木県</option>
                <option value="群馬県">群馬県</option>
                <option value="埼玉県">埼玉県</option>
                <option value="千葉県">千葉県</option>
                <option value="東京都">東京都</option>
                <option value="神奈川県">神奈川県</option>
                <option value="新潟県">新潟県</option>
                <option value="富山県">富山県</option>
                <option value="石川県">石川県</option>
                <option value="福井県">福井県</option>
                <option value="山梨県">山梨県</option>
                <option value="長野県">長野県</option>
                <option value="岐阜県">岐阜県</option>
                <option value="静岡県">静岡県</option>
                <option value="愛知県">愛知県</option>
                <option value="三重県">三重県</option>
                <option value="滋賀県">滋賀県</option>
                <option value="京都府">京都府</option>
                <option value="大阪府">大阪府</option>
                <option value="兵庫県">兵庫県</option>
                <option value="奈良県">奈良県</option>
                <option value="和歌山県">和歌山県</option>
                <option value="鳥取県">鳥取県</option>
                <option value="島根県">島根県</option>
                <option value="岡山県">岡山県</option>
                <option value="広島県">広島県</option>
                <option value="山口県">山口県</option>
                <option value="徳島県">徳島県</option>
                <option value="香川県">香川県</option>
                <option value="愛媛県">愛媛県</option>
                <option value="高知県">高知県</option>
                <option value="福岡県">福岡県</option>
                <option value="佐賀県">佐賀県</option>
                <option value="長崎県">長崎県</option>
                <option value="熊本県">熊本県</option>
                <option value="大分県">大分県</option>
                <option value="宮崎県">宮崎県</option>
                <option value="鹿児島県">鹿児島県</option>
                <option value="沖縄県">沖縄県</option>
              </select>
            </div>

            <div className="form-group">
              <label htmlFor="clientIndustry">取引先の主な業種</label>
              <input
                id="clientIndustry"
                type="text"
                value={userInfo.clientIndustry || ''}
                onChange={(e) => setUserInfo({ ...userInfo, clientIndustry: e.target.value || undefined })}
                placeholder="例: 製造業、建設業など"
                className="form-input"
              />
            </div>

            <div className="form-group">
              <label htmlFor="priceTransferStatus">現在の価格転嫁の状況</label>
              <select
                id="priceTransferStatus"
                value={userInfo.priceTransferStatus || ''}
                onChange={(e) => setUserInfo({ ...userInfo, priceTransferStatus: e.target.value || undefined })}
                className="form-input"
              >
                <option value="">選択してください</option>
                <option value="検討中">検討中</option>
                <option value="準備中">準備中</option>
                <option value="交渉中">交渉中</option>
                <option value="実施済み">実施済み</option>
                <option value="その他">その他</option>
              </select>
            </div>

            <div className="modal-buttons">
              <button onClick={handleUserInfoSubmit} className="submit-button">
                登録して開始
              </button>
            </div>
          </div>
        </div>
      )}

      <header className="app-header">
        <h1>価格転嫁支援AIアシスタント</h1>
        <button onClick={handleClear} className="clear-button">
          履歴クリア
        </button>
      </header>

      {currentStep && (
        <div className="step-indicator">
          📌 現在のステップ: <strong>{formatStepName(currentStep)}</strong>
        </div>
      )}

      <div className="chat-container">
        <div className="messages">
          {messages.map((msg, idx) => {
            // 最後のメッセージがアシスタントで、かつローディング中の場合、カーソルを表示
            const isLastMessage = idx === messages.length - 1
            const isAssistantLoading = isLastMessage && msg.role === 'assistant' && isLoading
            // このメッセージに図が紐づいているかどうか
            const hasDiagram = msg.role === 'assistant' && diagramMessageIndex === idx && latestDiagram
            
            return (
              <div key={idx}>
                <div className={`message ${msg.role}`}>
                  <div className="message-content">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                    {isAssistantLoading && currentStatus && (
                      <div className="status-message">
                        {currentStatus}
                      </div>
                    )}
                    {/* テキストが生成されている場合のみカーソルを表示（ステータス表示中は非表示） */}
                    {isAssistantLoading && !currentStatus && currentResponseRef.current.trim() && (
                      <span className="cursor">▌</span>
                    )}
                  </div>
                </div>
                {/* アシスタントメッセージの下に価格転嫁検討ツールのボタンを表示（STEP_0_CHECK_9の場合） */}
                {msg.role === 'assistant' && !isAssistantLoading && currentStep === 'STEP_0_CHECK_9' && idx === messages.length - 1 && (
                  <div style={{ marginTop: '0.5rem', marginBottom: '1rem', paddingLeft: '1rem' }}>
                    <button
                      onClick={() => setShowCostAnalysisModal(true)}
                      className="cost-analysis-button"
                      style={{
                        padding: '0.75rem 1.5rem',
                        backgroundColor: '#2a2a2a',
                        color: '#ffffff',
                        border: 'none',
                        borderRadius: '8px',
                        cursor: 'pointer',
                        fontSize: '0.9375rem',
                        fontWeight: '500',
                        boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
                        transition: 'background-color 0.2s'
                      }}
                      onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#3a3a3a'}
                      onMouseLeave={(e) => e.currentTarget.style.backgroundColor = '#2a2a2a'}
                    >
                      📊 価格転嫁検討ツールで分析する
                    </button>
                  </div>
                )}
                {/* 図が紐づいているメッセージの直後に図を表示 */}
                {hasDiagram && (
                  <div className="diagram-container">
                    <h3>📊 生成された図</h3>
                    <img src={`${API_BASE_URL}${latestDiagram}`} alt="生成された図" className="diagram-image" />
                  </div>
                )}
              </div>
            )
          })}
          {isLoading && messages.length > 0 && messages[messages.length - 1].role !== 'assistant' && (
            <div className="message assistant">
              <div className="message-content">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{currentResponseRef.current || ''}</ReactMarkdown>
                {currentStatus && (
                  <div className="status-message">
                    {currentStatus}
                  </div>
                )}
                {/* テキストが生成されている場合のみカーソルを表示（ステータス表示中は非表示） */}
                {!currentStatus && currentResponseRef.current.trim() && (
                  <span className="cursor">▌</span>
                )}
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="input-container">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && !isLoading && handleSend()}
            placeholder="メッセージを入力してください"
            disabled={isLoading || !sessionId}
            className="input-field"
          />
          {isLoading ? (
            <button
              onClick={handleStop}
              className="stop-button"
            >
              停止
            </button>
          ) : (
            <button
              onClick={() => handleSend()}
              disabled={!input.trim() || !sessionId}
              className="send-button"
            >
              送信
            </button>
          )}
        </div>
      </div>

      {/* 価格転嫁検討ツールモーダル */}
      {showCostAnalysisModal && (
        <div className="modal-overlay" onClick={() => !isAnalyzing && setShowCostAnalysisModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '700px' }}>
            <h2>価格転嫁検討ツール</h2>
            <p className="modal-description">
              コスト高騰前と現在のデータを入力して、価格転嫁の必要性を分析します。<br />
              決算書等から数値を入力してください。
            </p>

            <div style={{ marginBottom: '2rem' }}>
              <h3 style={{ fontSize: '1.1rem', marginBottom: '1rem', borderBottom: '2px solid #e0e0e0', paddingBottom: '0.5rem' }}>
                コスト高騰前の情報
              </h3>
              <div className="form-group">
                <label htmlFor="before_sales">売上高（円）</label>
                <input
                  id="before_sales"
                  type="number"
                  value={costAnalysisData.before_sales}
                  onChange={(e) => setCostAnalysisData({ ...costAnalysisData, before_sales: e.target.value })}
                  placeholder="例: 10000000"
                  className="form-input"
                  disabled={isAnalyzing}
                />
              </div>
              <div className="form-group">
                <label htmlFor="before_cost">売上原価（円）</label>
                <input
                  id="before_cost"
                  type="number"
                  value={costAnalysisData.before_cost}
                  onChange={(e) => setCostAnalysisData({ ...costAnalysisData, before_cost: e.target.value })}
                  placeholder="例: 6000000"
                  className="form-input"
                  disabled={isAnalyzing}
                />
              </div>
              <div className="form-group">
                <label htmlFor="before_expenses">販管費・その他経費（円）</label>
                <input
                  id="before_expenses"
                  type="number"
                  value={costAnalysisData.before_expenses}
                  onChange={(e) => setCostAnalysisData({ ...costAnalysisData, before_expenses: e.target.value })}
                  placeholder="例: 2000000"
                  className="form-input"
                  disabled={isAnalyzing}
                />
              </div>
            </div>

            <div style={{ marginBottom: '2rem' }}>
              <h3 style={{ fontSize: '1.1rem', marginBottom: '1rem', borderBottom: '2px solid #e0e0e0', paddingBottom: '0.5rem' }}>
                現在の情報
              </h3>
              <div className="form-group">
                <label htmlFor="current_sales">売上高（円）</label>
                <input
                  id="current_sales"
                  type="number"
                  value={costAnalysisData.current_sales}
                  onChange={(e) => setCostAnalysisData({ ...costAnalysisData, current_sales: e.target.value })}
                  placeholder="例: 10000000"
                  className="form-input"
                  disabled={isAnalyzing}
                />
              </div>
              <div className="form-group">
                <label htmlFor="current_cost">売上原価（円）</label>
                <input
                  id="current_cost"
                  type="number"
                  value={costAnalysisData.current_cost}
                  onChange={(e) => setCostAnalysisData({ ...costAnalysisData, current_cost: e.target.value })}
                  placeholder="例: 7000000"
                  className="form-input"
                  disabled={isAnalyzing}
                />
              </div>
              <div className="form-group">
                <label htmlFor="current_expenses">販管費・その他経費（円）</label>
                <input
                  id="current_expenses"
                  type="number"
                  value={costAnalysisData.current_expenses}
                  onChange={(e) => setCostAnalysisData({ ...costAnalysisData, current_expenses: e.target.value })}
                  placeholder="例: 2000000"
                  className="form-input"
                  disabled={isAnalyzing}
                />
              </div>
            </div>

            <div className="modal-buttons">
              <button
                onClick={handleCostAnalysisSubmit}
                className="submit-button"
                disabled={isAnalyzing}
              >
                {isAnalyzing ? '分析中...' : '分析実行'}
              </button>
              <button
                onClick={() => setShowCostAnalysisModal(false)}
                className="skip-button"
                disabled={isAnalyzing}
                style={{
                  padding: '0.875rem 2rem',
                  backgroundColor: 'transparent',
                  color: '#666666',
                  border: '1px solid #d8d8d8',
                  borderRadius: '8px',
                  cursor: isAnalyzing ? 'not-allowed' : 'pointer',
                  fontSize: '0.9375rem',
                  fontFamily: 'inherit'
                }}
              >
                キャンセル
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default App

