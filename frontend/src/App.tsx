import { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import ReactMarkdown from 'react-markdown'
import './App.css'

// Viteのプロキシ設定により、相対パスでアクセス
const API_BASE_URL = ''

interface Message {
  role: 'user' | 'assistant'
  content: string
}

interface ChatEvent {
  type: 'content' | 'tool_use' | 'step_update' | 'done' | 'error'
  data?: string
  tool?: string
  step?: string
  confidence?: string
  reasoning?: string
  content?: string
  error?: string
}

interface UserInfo {
  industry?: string
  products?: string
  companySize?: string
  region?: string
  clientIndustry?: string
  priceTransferStatus?: string
}

function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [currentStep, setCurrentStep] = useState<string | null>(null)
  const [latestDiagram, setLatestDiagram] = useState<string | null>(null)
  const [showUserInfoModal, setShowUserInfoModal] = useState(true)
  const [userInfo, setUserInfo] = useState<UserInfo>({})
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const currentResponseRef = useRef<string>('')

  // セッション初期化（ユーザー情報入力後）
  const initSession = async (userInfo: UserInfo) => {
    try {
      const response = await axios.post(`${API_BASE_URL}/api/session`, { user_info: userInfo })
      setSessionId(response.data.session_id)
      
      // ウェルカムメッセージ（ユーザー情報に基づいてカスタマイズ）
      let welcomeContent = `こんにちは！価格転嫁支援AIアシスタントです。

私は中小企業の皆様の価格転嫁をサポートするために設計されました。`

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

  // 最新の図を取得
  useEffect(() => {
    const fetchLatestDiagram = async () => {
      try {
        const response = await axios.get(`${API_BASE_URL}/api/diagrams/latest`)
        if (response.data.diagram) {
          // URLを直接使用
          setLatestDiagram(response.data.diagram.url)
        } else {
          setLatestDiagram(null)
        }
      } catch (error) {
        console.error('図の取得エラー:', error)
      }
    }
    
    const interval = setInterval(fetchLatestDiagram, 2000) // 2秒ごとにチェック
    return () => clearInterval(interval)
  }, [])

  // メッセージが更新されたらスクロール
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async () => {
    if (!input.trim() || !sessionId || isLoading) return

    const userMessage: Message = { role: 'user', content: input }
    setMessages(prev => [...prev, userMessage])
    setInput('')
    setIsLoading(true)
    currentResponseRef.current = ''

    try {
      const response = await fetch(`${API_BASE_URL}/api/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: input,
          session_id: sessionId,
        }),
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
              } else if (event.type === 'tool_use') {
                // ツール使用中の表示
                const toolMessage = `\n\n*[${event.tool} を使用中]*\n\n`
                currentResponseRef.current += toolMessage
                
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
              } else if (event.type === 'step_update') {
                setCurrentStep(event.step || null)
                // ステップ更新通知をメッセージに追加
                const stepMessage = `\n\n**📌 ステップ判定: ${event.step}** (信頼度: ${event.confidence})\n${event.reasoning}\n\n`
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
    } catch (error) {
      console.error('チャットエラー:', error)
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: `❌ エラーが発生しました: ${error}` },
      ])
    } finally {
      setIsLoading(false)
    }
  }

  const handleClear = async () => {
    if (!sessionId) return

    try {
      await axios.post(`${API_BASE_URL}/api/session/${sessionId}/clear`)
      setMessages([])
      setCurrentStep(null)
      setLatestDiagram(null)
      
      // ウェルカムメッセージを再表示
      const welcomeMessage: Message = {
        role: 'assistant',
        content: `こんにちは！価格転嫁支援AIアシスタントです。

私は中小企業の皆様の価格転嫁をサポートするために設計されました。

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
          📌 現在のステップ: <strong>{currentStep}</strong>
        </div>
      )}

      <div className="chat-container">
        <div className="messages">
          {messages.map((msg, idx) => {
            // 最後のメッセージがアシスタントで、かつローディング中の場合、カーソルを表示
            const isLastMessage = idx === messages.length - 1
            const isAssistantLoading = isLastMessage && msg.role === 'assistant' && isLoading
            
            return (
              <div key={idx} className={`message ${msg.role}`}>
                <div className="message-content">
                  <ReactMarkdown>{msg.content}</ReactMarkdown>
                  {isAssistantLoading && <span className="cursor">▌</span>}
                </div>
              </div>
            )
          })}
          {isLoading && messages.length > 0 && messages[messages.length - 1].role !== 'assistant' && (
            <div className="message assistant">
              <div className="message-content">
                <ReactMarkdown>{currentResponseRef.current || '考え中...'}</ReactMarkdown>
                <span className="cursor">▌</span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {latestDiagram && (
          <div className="diagram-container">
            <h3>📊 生成された図</h3>
            <img src={`${API_BASE_URL}${latestDiagram}`} alt="生成された図" className="diagram-image" />
          </div>
        )}

        <div className="input-container">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSend()}
            placeholder="メッセージを入力してください"
            disabled={isLoading || !sessionId}
            className="input-field"
          />
          <button
            onClick={handleSend}
            disabled={isLoading || !input.trim() || !sessionId}
            className="send-button"
          >
            送信
          </button>
        </div>
      </div>
    </div>
  )
}

export default App

