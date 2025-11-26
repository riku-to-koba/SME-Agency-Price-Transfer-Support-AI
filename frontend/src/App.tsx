import { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import './App.css'
import { ToolModal } from './components/ToolModal'
import { InlineCostForm } from './components/InlineCostForm'
import { MODAL_CONFIGS, TOOL_TO_MODAL_MAP, ModalType } from './config/modal-config'

// Viteのプロキシ設定により、相対パスでアクセス
const API_BASE_URL = ''

interface Message {
  role: 'user' | 'assistant'
  content: string
  images?: string[]  // Base64画像データの配列
  pdfs?: string[]    // Base64 PDFデータの配列
  inlineFormType?: 'cost_form'  // チャット内フォームのタイプ
  formSubmitted?: boolean  // フォームが送信済みかどうか
}

interface ChatEvent {
  type: 'content' | 'tool_use' | 'step_update' | 'mode_update' | 'done' | 'error' | 'status' | 'image' | 'pdf' | 'show_modal'
  data?: string
  tool?: string
  show_modal?: boolean
  modal_type?: ModalType
  step?: string
  mode?: string
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
}

interface CostAnalysisData {
  before_sales: string
  before_cost: string
  before_expenses: string
  current_sales: string
  current_cost: string
  current_expenses: string
}


function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [currentMode, setCurrentMode] = useState<string | null>(null)
  const [currentStep, setCurrentStep] = useState<string | null>(null)
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
  // 汎用ツールモーダル用のstate
  const [activeModalType, setActiveModalType] = useState<ModalType | null>(null)
  const [isModalLoading, setIsModalLoading] = useState(false)
  const [currentStatus, setCurrentStatus] = useState<string>('') // 現在のステータスメッセージ
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const currentResponseRef = useRef<string>('')
  const currentImagesRef = useRef<string[]>([])  // 現在のメッセージに紐づく画像
  const currentPdfsRef = useRef<string[]>([])    // 現在のメッセージに紐づくPDF
  const abortControllerRef = useRef<AbortController | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // セッション初期化（ユーザー情報入力後）
  const initSession = async (userInfo: UserInfo) => {
    try {
      const response = await axios.post(`${API_BASE_URL}/api/session`, { user_info: userInfo })
      setSessionId(response.data.session_id)
      
      // ウェルカムメッセージ（ユーザー情報に基づいてカスタマイズ）
      let welcomeContent = `こんにちは！中小企業価格転嫁サポートAIです。

資金繰り、人材、販路拡大、価格交渉、事業承継…
経営のお悩み、どんなことでも気軽にご相談ください。`

      // 基本情報を整理して表示
      const infoItems: string[] = []
      if (userInfo.industry) infoItems.push(`業種: ${userInfo.industry}`)
      if (userInfo.products) infoItems.push(`主な製品・サービス: ${userInfo.products}`)
      if (userInfo.companySize) infoItems.push(`従業員規模: ${userInfo.companySize}`)
      if (userInfo.region) infoItems.push(`地域: ${userInfo.region}`)
      if (userInfo.clientIndustry) infoItems.push(`取引先の主な業種: ${userInfo.clientIndustry}`)
      
      if (infoItems.length > 0) {
        welcomeContent += `\n\n**📋 ご登録いただいた基本情報**\n\n`
        infoItems.forEach(item => {
          welcomeContent += `- ${item}\n`
        })
        welcomeContent += `\n上記の情報を踏まえて、より具体的で実践的なアドバイスを提供させていただきます。`
      }

      welcomeContent += `

**できること:**
- 経営全般のご相談（資金繰り、人材、販路拡大など）
- 価格交渉・値上げ交渉の専門サポート
- 市場データ分析、コスト試算、交渉資料作成
- 業界動向の検索とデータ可視化

**使い方:**
お困りのことや知りたいことを、お気軽にご質問ください。
例: 「資金繰りで困っている」「値上げ交渉の準備をしたい」「業界の動向を知りたい」

今日はどんなことでお困りですか？`

      const welcomeMessage: Message = {
        role: 'assistant',
        content: welcomeContent
      }
      setMessages([welcomeMessage])
    } catch (error) {
      console.error('セッション初期化エラー:', error)
      // エラー時もウェルカムメッセージを表示
      const errorMessage: Message = {
        role: 'assistant',
        content: `こんにちは！中小企業価格転嫁サポートAIです。

申し訳ございませんが、セッションの初期化でエラーが発生しました。
再度お試しください。

今日はどんなことでお困りですか？`
      }
      setMessages([errorMessage])
    }
  }

  // ユーザー情報送信ハンドラ
  const handleUserInfoSubmit = () => {
    setShowUserInfoModal(false)
    initSession(userInfo)
  }

  // メッセージが更新されたらスクロール
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // textareaの高さを自動調整
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`
    }
  }, [input])

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
              images: currentImagesRef.current.length > 0 ? [...currentImagesRef.current] : undefined,
              pdfs: currentPdfsRef.current.length > 0 ? [...currentPdfsRef.current] : undefined,
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
      // textareaの高さをリセット
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto'
      }
    }
    setIsLoading(true)
    currentResponseRef.current = ''
    currentImagesRef.current = []  // 画像リストをリセット
    currentPdfsRef.current = []    // PDFリストをリセット

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
      let formMessageAdded = false  // フォームメッセージが追加されたかどうか
      let contentMessageIndex = -1  // コンテンツメッセージのインデックス

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

                  // フォームメッセージが追加されている場合は、新しいメッセージとして追加
                  if (formMessageAdded && contentMessageIndex === -1) {
                    // フォームの後に新しいコンテンツメッセージを追加
                    setMessages(prev => {
                      contentMessageIndex = prev.length
                      return [...prev, {
                        role: 'assistant',
                        content: currentResponseRef.current,
                        images: currentImagesRef.current.length > 0 ? [...currentImagesRef.current] : undefined,
                        pdfs: currentPdfsRef.current.length > 0 ? [...currentPdfsRef.current] : undefined,
                      }]
                    })
                    hasAddedAssistantMessage = true
                  } else if (!hasAddedAssistantMessage) {
                    // 最初のcontentイベントでアシスタントメッセージを追加
                    hasAddedAssistantMessage = true
                    setMessages(prev => {
                      contentMessageIndex = prev.length
                      return [...prev, {
                        role: 'assistant',
                        content: currentResponseRef.current,
                        images: currentImagesRef.current.length > 0 ? [...currentImagesRef.current] : undefined,
                        pdfs: currentPdfsRef.current.length > 0 ? [...currentPdfsRef.current] : undefined,
                      }]
                    })
                  } else {
                    // 既存のメッセージを更新（フォームメッセージは上書きしない）
                    setMessages(prev => {
                      const newMessages = [...prev]
                      // contentMessageIndexが設定されていればそれを使う、なければ最後のメッセージ
                      const targetIndex = contentMessageIndex >= 0 ? contentMessageIndex : newMessages.length - 1
                      // フォームメッセージでなければ更新
                      if (!newMessages[targetIndex]?.inlineFormType) {
                        newMessages[targetIndex] = {
                          role: 'assistant',
                          content: currentResponseRef.current,
                          images: currentImagesRef.current.length > 0 ? [...currentImagesRef.current] : undefined,
                          pdfs: currentPdfsRef.current.length > 0 ? [...currentPdfsRef.current] : undefined,
                        }
                      }
                      return newMessages
                    })
                  }
                } else if (event.type === 'image') {
                  // 画像データを受信
                  if (event.data) {
                    currentImagesRef.current.push(event.data)

                    // メッセージを更新して画像を追加（フォームメッセージは上書きしない）
                    if (hasAddedAssistantMessage) {
                      setMessages(prev => {
                        const newMessages = [...prev]
                        const targetIndex = contentMessageIndex >= 0 ? contentMessageIndex : newMessages.length - 1
                        if (!newMessages[targetIndex]?.inlineFormType) {
                          newMessages[targetIndex] = {
                            role: 'assistant',
                            content: currentResponseRef.current,
                            images: [...currentImagesRef.current],
                            pdfs: currentPdfsRef.current.length > 0 ? [...currentPdfsRef.current] : undefined,
                          }
                        }
                        return newMessages
                      })
                    }
                  }
                } else if (event.type === 'pdf') {
                  // PDFデータを受信
                  if (event.data) {
                    currentPdfsRef.current.push(event.data)

                    // メッセージを更新してPDFを追加（フォームメッセージは上書きしない）
                    if (hasAddedAssistantMessage) {
                      setMessages(prev => {
                        const newMessages = [...prev]
                        const targetIndex = contentMessageIndex >= 0 ? contentMessageIndex : newMessages.length - 1
                        if (!newMessages[targetIndex]?.inlineFormType) {
                          newMessages[targetIndex] = {
                            role: 'assistant',
                            content: currentResponseRef.current,
                            images: currentImagesRef.current.length > 0 ? [...currentImagesRef.current] : undefined,
                            pdfs: [...currentPdfsRef.current],
                          }
                        }
                        return newMessages
                      })
                    }
                  }
                } else if (event.type === 'status') {
                  // ステータス更新（思考中、検索中など）
                  if (event.status === 'none') {
                    setCurrentStatus('')
                  } else {
                    setCurrentStatus(event.message || '')
                  }
                } else if (event.type === 'mode_update') {
                  // モード更新
                  setCurrentMode(event.mode || null)
                  console.log(`[モード更新] ${event.mode}`)
                } else if (event.type === 'tool_use') {
                                  // ツール使用中
                                  console.log(`[ツール使用中] ${event.tool}`)
                                  
                                  // ツール名からフォーム種別を判定
                                  if (event.tool && event.show_modal) {
                                    const modalType = TOOL_TO_MODAL_MAP[event.tool]
                                    if (modalType === 'ideal_pricing') {
                                      // チャット内フォームとして表示
                                      const formMessage: Message = {
                                        role: 'assistant',
                                        content: '原価計算を行います。以下のフォームに情報を入力してください。',
                                        inlineFormType: 'cost_form',
                                        formSubmitted: false,
                                      }
                                      setMessages(prev => [...prev, formMessage])
                                      formMessageAdded = true  // フォームメッセージが追加されたことを記録
                                      hasAddedAssistantMessage = true
                                    } else if (event.tool === 'analyze_cost_impact') {
                                      // 後方互換性: 既存のモーダル
                                      setShowCostAnalysisModal(true)
                                    }
                                  }
                                } else if (event.type === 'show_modal') {
                                  // 直接モーダル表示リクエスト（チャット内フォームに変換）
                                  if (event.modal_type === 'ideal_pricing') {
                                    const formMessage: Message = {
                                      role: 'assistant',
                                      content: '原価計算を行います。以下のフォームに情報を入力してください。',
                                      inlineFormType: 'cost_form',
                                      formSubmitted: false,
                                    }
                                    setMessages(prev => [...prev, formMessage])
                                    formMessageAdded = true  // フォームメッセージが追加されたことを記録
                                    hasAddedAssistantMessage = true
                                  } else if (event.modal_type) {
                                    setActiveModalType(event.modal_type)
                                  }
                                } else if (event.type === 'step_update') {
                  // ステップ更新（後方互換性のため維持）
                  setCurrentStep(event.step || null)
                } else if (event.type === 'done') {
                  // ステータスをクリア
                  setCurrentStatus('')

                  // フォームメッセージのみの場合はスキップ（テキストコンテンツなし）
                  if (formMessageAdded && !currentResponseRef.current.trim()) {
                    // フォームメッセージのみなので何もしない
                    continue
                  }

                  // アシスタントメッセージがまだ追加されていない場合は追加
                  if (!hasAddedAssistantMessage) {
                    hasAddedAssistantMessage = true
                    setMessages(prev => [...prev, {
                      role: 'assistant',
                      content: event.content || currentResponseRef.current,
                      images: currentImagesRef.current.length > 0 ? [...currentImagesRef.current] : undefined,
                      pdfs: currentPdfsRef.current.length > 0 ? [...currentPdfsRef.current] : undefined,
                    }])
                  } else {
                    // フォームメッセージを上書きしない
                    setMessages(prev => {
                      const newMessages = [...prev]
                      const targetIndex = contentMessageIndex >= 0 ? contentMessageIndex : newMessages.length - 1
                      if (!newMessages[targetIndex]?.inlineFormType) {
                        newMessages[targetIndex] = {
                          role: 'assistant',
                          content: event.content || currentResponseRef.current,
                          images: currentImagesRef.current.length > 0 ? [...currentImagesRef.current] : undefined,
                          pdfs: currentPdfsRef.current.length > 0 ? [...currentPdfsRef.current] : undefined,
                        }
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
        const agentRequest = `価格転嫁検討ツールで分析しました。以下の分析結果を要約して、分かりやすく説明してください。また、このデータを使って generate_chart ツールで棒グラフも生成してください。

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

  // チャット内フォームの送信処理
  const handleInlineCostFormSubmit = async (data: Record<string, number | null>, messageIndex: number) => {
    // フォームを送信済みに更新
    setMessages(prev => {
      const newMessages = [...prev]
      if (newMessages[messageIndex]) {
        newMessages[messageIndex] = {
          ...newMessages[messageIndex],
          formSubmitted: true,
        }
      }
      return newMessages
    })

    // 入力データをLLM用のメッセージに整形
    const costTypeNames: Record<string, string> = {
      material_cost: '仕入れ・材料費',
      labor_cost: '人件費',
      energy_cost: '光熱費',
      overhead: 'その他経費',
    }

    const costDetails: string[] = []
    
    // 売上
    if (data.previous_sales || data.current_sales) {
      costDetails.push(`- 月の売上: 以前 ${data.previous_sales || '未入力'}万円 → 現在 ${data.current_sales || '未入力'}万円`)
    }
    
    // 各費目
    const costFields = [
      { prev: 'material_cost_previous', curr: 'material_cost_current', name: '仕入れ・材料費' },
      { prev: 'labor_cost_previous', curr: 'labor_cost_current', name: '人件費' },
      { prev: 'energy_cost_previous', curr: 'energy_cost_current', name: '光熱費' },
      { prev: 'overhead_previous', curr: 'overhead_current', name: 'その他経費' },
    ]
    
    for (const field of costFields) {
      if (data[field.prev] || data[field.curr]) {
        costDetails.push(`- ${field.name}: 以前 ${data[field.prev] || '未入力'}万円 → 現在 ${data[field.curr] || '未入力'}万円`)
      }
    }

    // LLMに送信するメッセージ
    const agentRequest = `【原価情報の入力結果】
以下のコスト情報を基に、価格転嫁の分析と松竹梅（理想・妥当・最低防衛ライン）の値上げ率を計算してください。

${costDetails.join('\n')}

※ 未入力の項目は業界平均で推計してください。
※ 松竹梅の3パターンで値上げ率と利益率を提示してください。
※ 推奨シナリオと次のアクションも提案してください。`

    // LLMに送信（ユーザーメッセージは表示しない）
    setTimeout(() => {
      handleSend(agentRequest, true)
    }, 300)
  }

  // チャット内フォームのスキップ処理
  const handleInlineCostFormSkip = (messageIndex: number) => {
    // フォームを送信済みに更新（スキップ表示に変更）
    setMessages(prev => {
      const newMessages = [...prev]
      if (newMessages[messageIndex]) {
        newMessages[messageIndex] = {
          ...newMessages[messageIndex],
          content: '原価計算をスキップしました。後からいつでも「原価計算をしたい」と言っていただければ、再度フォームを表示できます。',
          inlineFormType: undefined,
        }
      }
      return newMessages
    })
  }

  // 汎用ツールモーダルの送信処理
  const handleToolModalSubmit = async (data: Record<string, number | string>) => {
    if (!activeModalType) return

    const config = MODAL_CONFIGS[activeModalType]
    setIsModalLoading(true)

    try {
      const response = await axios.post(`${API_BASE_URL}${config.apiEndpoint}`, data)

      if (response.data.success) {
        const result = response.data.result

        // モーダルを閉じる
        setActiveModalType(null)

        // 結果に基づいてエージェントにメッセージを送信
        if (activeModalType === 'ideal_pricing') {
          // 理想の原価計算の結果をフォーマット
          const scenarios = result.scenarios
          const recommendation = result.recommendation
          const costStructure = result.cost_structure
          const profitAnalysis = result.profit_analysis

          const resultText = `【理想の原価計算 - 分析結果】

【コスト構造の変化】
- 材料費: ${costStructure.before.material_cost.toLocaleString()}円 → ${costStructure.after.material_cost.toLocaleString()}円 (+${costStructure.changes.material_cost}%)
- 労務費: ${costStructure.before.labor_cost.toLocaleString()}円 → ${costStructure.after.labor_cost.toLocaleString()}円 (+${costStructure.changes.labor_cost}%)
- エネルギー費: ${costStructure.before.energy_cost.toLocaleString()}円 → ${costStructure.after.energy_cost.toLocaleString()}円 (+${costStructure.changes.energy_cost}%)
- その他経費: ${costStructure.before.overhead.toLocaleString()}円 → ${costStructure.after.overhead.toLocaleString()}円 (+${costStructure.changes.overhead}%)
- **総コスト: ${costStructure.before.total.toLocaleString()}円 → ${costStructure.after.total.toLocaleString()}円 (+${costStructure.total_increase_rate.toFixed(1)}%)**

【利益への影響】
- 現在の売上高: ${profitAnalysis.current_sales.toLocaleString()}円
- コスト高騰前の利益率: ${profitAnalysis.before_profit_rate.toFixed(1)}%
- 価格据え置き時の利益率: ${profitAnalysis.after_profit_rate_if_unchanged.toFixed(1)}%

【価格改定シナリオ（松竹梅）】
🌟 **${scenarios.premium.name}**
   - 目標価格: ${Math.round(scenarios.premium.target_price).toLocaleString()}円（+${scenarios.premium.price_increase_rate.toFixed(1)}%）
   - 利益率: ${scenarios.premium.profit_margin.toFixed(1)}%
   - ${scenarios.premium.description}

✅ **${scenarios.standard.name}**
   - 目標価格: ${Math.round(scenarios.standard.target_price).toLocaleString()}円（+${scenarios.standard.price_increase_rate.toFixed(1)}%）
   - 利益率: ${scenarios.standard.profit_margin.toFixed(1)}%
   - ${scenarios.standard.description}

⚡ **${scenarios.minimum.name}**
   - 目標価格: ${Math.round(scenarios.minimum.target_price).toLocaleString()}円（+${scenarios.minimum.price_increase_rate.toFixed(1)}%）
   - 利益率: ${scenarios.minimum.profit_margin.toFixed(1)}%
   - ${scenarios.minimum.description}

【推奨】
緊急度: ${recommendation.urgency === 'high' ? '🚨 高' : recommendation.urgency === 'medium' ? '⚠️ 中' : '📝 低'}
${recommendation.urgency_message}
推奨シナリオ: ${scenarios[recommendation.recommended_scenario].name}`

          // エージェントに要約を依頼
          const agentRequest = `理想の原価計算ツールで分析しました。以下の分析結果を要約して、ユーザーに分かりやすく説明してください。また、必要に応じてグラフ化も検討してください。

${resultText}`

          setTimeout(() => {
            handleSend(agentRequest, true)
          }, 300)
        }
      } else {
        alert(`エラー: ${response.data.message}`)
      }
    } catch (error: any) {
      console.error('ツールモーダルエラー:', error)
      alert(`エラーが発生しました: ${error.response?.data?.message || error.message}`)
    } finally {
      setIsModalLoading(false)
    }
  }

  const handleClear = async () => {
    if (!sessionId) return

    try {
      await axios.post(`${API_BASE_URL}/api/session/${sessionId}/clear`)
      setMessages([])
      setCurrentStep(null)
      
      // ウェルカムメッセージを再表示
      const welcomeMessage: Message = {
        role: 'assistant',
        content: `こんにちは！中小企業価格転嫁サポートAIです。

資金繰り、人材、販路拡大、価格交渉、事業承継…
経営のお悩み、どんなことでも気軽にご相談ください。

**できること:**
- 経営全般のご相談（資金繰り、人材、販路拡大など）
- 価格交渉・値上げ交渉の専門サポート
- 市場データ分析、コスト試算、交渉資料作成
- 業界動向の検索とデータ可視化

**使い方:**
お困りのことや知りたいことを、お気軽にご質問ください。
例: 「資金繰りで困っている」「値上げ交渉の準備をしたい」「業界の動向を知りたい」

今日はどんなことでお困りですか？`
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

            <div className="modal-buttons">
              <button onClick={handleUserInfoSubmit} className="submit-button">
                登録して開始
              </button>
            </div>
          </div>
        </div>
      )}

      <header className="app-header">
        <h1>中小企業価格転嫁サポートAI</h1>
        <div className="header-controls">
          {currentMode && (
            <div className={`mode-badge ${currentMode}`}>
              {currentMode === 'mode1' ? '💼 よろず相談' : '💰 価格転嫁専門'}
            </div>
          )}
          <button onClick={handleClear} className="clear-button">
            履歴クリア
          </button>
        </div>
      </header>

      <div className="chat-container">
        <div className="messages">
          {messages.map((msg, idx) => {
            // 最後のメッセージがアシスタントで、かつローディング中の場合、カーソルを表示
            const isLastMessage = idx === messages.length - 1
            const isAssistantLoading = isLastMessage && msg.role === 'assistant' && isLoading
            
            // メッセージ内からグラフURLを抽出（重複を除去）
            const chartUrlMatches = msg.content.match(/\[CHART_URL\](.*?)\[\/CHART_URL\]/g) || []
            const chartUrls = [...new Set(chartUrlMatches.map(m => m.replace(/\[CHART_URL\]|\[\/CHART_URL\]/g, '').trim()))]
            
            // メッセージ内からPDFファイル名を抽出
            const pdfFileMatches = msg.content.match(/\[PDF_FILE\](.*?)\[\/PDF_FILE\]/g) || []
            const pdfFilenames = pdfFileMatches.map(m => m.replace(/\[PDF_FILE\]|\[\/PDF_FILE\]/g, '').trim())
            
            // [PDF_FILE]タグがない場合、.pdfで終わるファイル名を検出（バックアップ）
            if (pdfFilenames.length === 0 && msg.content.includes('.pdf')) {
              const backupMatches = msg.content.match(/[a-zA-Z0-9_\-\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]+\.pdf/g)
              if (backupMatches) {
                pdfFilenames.push(...backupMatches)
              }
            }
            
            // PDFが生成されたかチェック（複数のパターンに対応）
            const hasPdfGenerated = 
              msg.content.includes('PDFを生成しました') || 
              msg.content.includes('PDF生成') ||
              msg.content.includes('ドキュメントを作成') ||
              msg.content.includes('文書を作成') ||
              (msg.content.includes('完成しました') && msg.content.includes('ドキュメント')) ||
              (msg.content.includes('作成いたしました') && msg.content.includes('ドキュメント')) ||
              msg.content.includes('generate_document')
            
            // 表示用にタグを除去したコンテンツ
            let displayContent = msg.content
              .replace(/\[PDF_FILE\].*?\[\/PDF_FILE\]/g, '')
              .replace(/\[CHART_URL\].*?\[\/CHART_URL\]/g, '')
              .trim()
            
            return (
              <div key={idx}>
                <div className={`message ${msg.role}`}>
                  <div className="message-content">
                    {msg.role === 'user' ? (
                      <div style={{ whiteSpace: 'pre-wrap' }}>{displayContent}</div>
                    ) : (
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{displayContent}</ReactMarkdown>
                    )}
                    {isAssistantLoading && currentStatus && (
                      <div className="status-message">
                        {currentStatus}
                      </div>
                    )}
                    {/* テキストが生成されている場合のみカーソルを表示（ステータス表示中は非表示） */}
                    {isAssistantLoading && !currentStatus && currentResponseRef.current.trim() && (
                      <span className="cursor">▌</span>
                    )}
                    {/* チャット内フォーム */}
                    {msg.inlineFormType === 'cost_form' && (
                      <InlineCostForm
                        onSubmit={(data) => handleInlineCostFormSubmit(data, idx)}
                        onSkip={() => handleInlineCostFormSkip(idx)}
                        isLoading={isModalLoading}
                        isSubmitted={msg.formSubmitted}
                      />
                    )}
                    {/* グラフ画像をURLから表示 */}
                    {chartUrls.length > 0 && (
                      <div className="message-images" style={{ marginTop: '16px' }}>
                        {chartUrls.map((chartUrl, imgIdx) => (
                          <div key={imgIdx} className="chart-image-container" style={{
                            backgroundColor: '#f8f9fa',
                            borderRadius: '8px',
                            padding: '12px',
                            marginBottom: '12px'
                          }}>
                            <img
                              src={`${API_BASE_URL}${chartUrl}`}
                              alt={`生成されたグラフ ${imgIdx + 1}`}
                              className="chart-image"
                              style={{
                                maxWidth: '100%',
                                borderRadius: '4px',
                                boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
                              }}
                              onError={(e) => {
                                console.error('画像読み込みエラー:', chartUrl)
                                e.currentTarget.style.display = 'none'
                              }}
                            />
                          </div>
                        ))}
                      </div>
                    )}
                    {/* このメッセージに紐づくBase64画像を表示（旧方式、互換性のため維持） */}
                    {msg.images && msg.images.length > 0 && (
                      <div className="message-images">
                        {msg.images.map((imgData, imgIdx) => (
                          <div key={imgIdx} className="chart-image-container">
                            <img
                              src={`data:image/png;base64,${imgData}`}
                              alt={`生成されたグラフ ${imgIdx + 1}`}
                              className="chart-image"
                            />
                          </div>
                        ))}
                      </div>
                    )}
                    {/* このメッセージに紐づくPDFを表示 */}
                    {msg.pdfs && msg.pdfs.length > 0 && (
                      <div className="message-pdfs">
                        {msg.pdfs.map((pdfData, pdfIdx) => {
                          const blob = new Blob([Uint8Array.from(atob(pdfData), c => c.charCodeAt(0))], { type: 'application/pdf' })
                          const url = URL.createObjectURL(blob)
                          return (
                            <div key={pdfIdx} style={{ marginTop: '12px', display: 'flex', gap: '8px' }}>
                              <a
                                href={url}
                                download={`document_${idx}_${pdfIdx}.pdf`}
                                style={{
                                  display: 'inline-block',
                                  padding: '8px 16px',
                                  backgroundColor: '#555',
                                  color: 'white',
                                  textDecoration: 'none',
                                  borderRadius: '4px',
                                  fontSize: '14px'
                                }}
                              >
                                ダウンロード
                              </a>
                              <a
                                href={url}
                                target="_blank"
                                rel="noopener noreferrer"
                                style={{
                                  display: 'inline-block',
                                  padding: '8px 16px',
                                  backgroundColor: 'transparent',
                                  color: '#555',
                                  textDecoration: 'none',
                                  borderRadius: '4px',
                                  fontSize: '14px',
                                  border: '1px solid #999'
                                }}
                              >
                                プレビュー
                              </a>
                            </div>
                          )
                        })}
                      </div>
                    )}
                    {/* ファイル名から検出したPDFのダウンロードボタン */}
                    {pdfFilenames.length > 0 && (
                      <div className="message-pdfs" style={{ marginTop: '12px' }}>
                        {pdfFilenames.map((filename, pdfIdx) => (
                          <div key={pdfIdx} style={{ marginTop: '8px', display: 'flex', gap: '8px' }}>
                            <a
                              href={`${API_BASE_URL}/api/documents/${filename}`}
                              download={filename}
                              style={{
                                display: 'inline-block',
                                padding: '8px 16px',
                                backgroundColor: '#555',
                                color: 'white',
                                textDecoration: 'none',
                                borderRadius: '4px',
                                fontSize: '14px'
                              }}
                            >
                              ダウンロード
                            </a>
                            <a
                              href={`${API_BASE_URL}/api/documents/${filename}/preview`}
                              target="_blank"
                              rel="noopener noreferrer"
                              style={{
                                display: 'inline-block',
                                padding: '8px 16px',
                                backgroundColor: 'transparent',
                                color: '#555',
                                textDecoration: 'none',
                                borderRadius: '4px',
                                fontSize: '14px',
                                border: '1px solid #999'
                              }}
                            >
                              プレビュー
                            </a>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
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
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey && !isLoading) {
                e.preventDefault()
                handleSend()
              }
            }}
            placeholder="メッセージを入力してください（Shift+Enterで改行）"
            disabled={isLoading || !sessionId}
            className="input-field"
            rows={1}
            style={{
              resize: 'none',
              minHeight: '48px',
              maxHeight: '200px',
              overflowY: 'auto',
            }}
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

      {/* 汎用ツールモーダル */}
      {activeModalType && MODAL_CONFIGS[activeModalType] && (
        <ToolModal
          config={MODAL_CONFIGS[activeModalType]}
          isOpen={true}
          onClose={() => setActiveModalType(null)}
          onSubmit={handleToolModalSubmit}
          isLoading={isModalLoading}
        />
      )}
    </div>
  )
}

export default App
