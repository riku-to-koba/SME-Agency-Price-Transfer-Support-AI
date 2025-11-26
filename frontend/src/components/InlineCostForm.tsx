/**
 * チャット内に埋め込まれる原価計算フォーム
 * モーダルではなく、メッセージとして表示される
 */

import { useState } from 'react'

interface InlineCostFormProps {
  onSubmit: (data: Record<string, number | null>) => void
  onSkip: () => void
  isLoading?: boolean
  isSubmitted?: boolean
}

interface CostField {
  id: string
  label: string
  previousKey: string
  currentKey: string
  placeholder: { previous: string; current: string }
}

const COST_FIELDS: CostField[] = [
  {
    id: 'sales',
    label: '月の売上',
    previousKey: 'previous_sales',
    currentKey: 'current_sales',
    placeholder: { previous: '例: 500', current: '例: 480' },
  },
  {
    id: 'material',
    label: '仕入れ・材料費',
    previousKey: 'material_cost_previous',
    currentKey: 'material_cost_current',
    placeholder: { previous: '例: 100', current: '例: 120' },
  },
  {
    id: 'labor',
    label: '人件費（給与+社保）',
    previousKey: 'labor_cost_previous',
    currentKey: 'labor_cost_current',
    placeholder: { previous: '例: 150', current: '例: 160' },
  },
  {
    id: 'energy',
    label: '光熱費（電気・ガス）',
    previousKey: 'energy_cost_previous',
    currentKey: 'energy_cost_current',
    placeholder: { previous: '例: 20', current: '例: 28' },
  },
  {
    id: 'overhead',
    label: 'その他経費',
    previousKey: 'overhead_previous',
    currentKey: 'overhead_current',
    placeholder: { previous: '例: 30', current: '例: 32' },
  },
]

export const InlineCostForm = ({
  onSubmit,
  onSkip,
  isLoading = false,
  isSubmitted = false,
}: InlineCostFormProps) => {
  const [formData, setFormData] = useState<Record<string, string>>({})
  const [error, setError] = useState<string>('')

  const handleChange = (key: string, value: string) => {
    setFormData((prev) => ({ ...prev, [key]: value }))
    setError('')
  }

  const handleSubmit = () => {
    // 少なくとも1つの費目が入力されているかチェック
    const hasAnyData = COST_FIELDS.some(
      (field) =>
        formData[field.previousKey] || formData[field.currentKey]
    )

    if (!hasAnyData) {
      setError('少なくとも1つの費目を入力してください')
      return
    }

    // すべてのフィールドを含むオブジェクトを作成（未入力はnull）
    const numericData: Record<string, number | null> = {}
    COST_FIELDS.forEach((field) => {
      const prevValue = formData[field.previousKey]
      const currValue = formData[field.currentKey]
      numericData[field.previousKey] = prevValue ? parseFloat(prevValue) : null
      numericData[field.currentKey] = currValue ? parseFloat(currValue) : null
    })

    onSubmit(numericData)
  }

  // 送信済みの場合は完了メッセージを表示
  if (isSubmitted) {
    return (
      <div style={{
        backgroundColor: '#f0f9f0',
        border: '1px solid #4CAF50',
        borderRadius: '8px',
        padding: '12px 16px',
        marginTop: '12px',
      }}>
        ✅ 原価計算が完了しました
      </div>
    )
  }

  return (
    <div style={{
      backgroundColor: '#f8f9fa',
      border: '1px solid #e0e0e0',
      borderRadius: '12px',
      padding: '20px',
      marginTop: '12px',
    }}>
      <h3 style={{
        margin: '0 0 8px 0',
        fontSize: '1.1rem',
        color: '#333',
      }}>
        📊 理想の原価計算
      </h3>
      <p style={{
        margin: '0 0 16px 0',
        fontSize: '0.9rem',
        color: '#666',
      }}>
        「以前」と「現在」の金額を入力してください（上昇率は自動計算）。
        <br />
        <span style={{ color: '#888' }}>※ 分からない項目は空欄でOK（業界平均で試算します）</span>
      </p>

      {error && (
        <div style={{
          backgroundColor: '#fee',
          border: '1px solid #e74c3c',
          borderRadius: '4px',
          padding: '8px 12px',
          marginBottom: '12px',
          color: '#c0392b',
          fontSize: '0.9rem',
        }}>
          ⚠️ {error}
        </div>
      )}

      {/* ヘッダー行 */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr 1fr',
        gap: '8px',
        marginBottom: '8px',
        fontWeight: 'bold',
        fontSize: '0.85rem',
        color: '#666',
      }}>
        <div></div>
        <div style={{ textAlign: 'center' }}>以前</div>
        <div style={{ textAlign: 'center' }}>現在</div>
      </div>

      {/* 入力フィールド */}
      {COST_FIELDS.map((field) => (
        <div
          key={field.id}
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr 1fr',
            gap: '8px',
            marginBottom: '8px',
            alignItems: 'center',
          }}
        >
          <label style={{
            fontSize: '0.9rem',
            color: '#333',
            fontWeight: '500',
          }}>
            {field.label}
          </label>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <input
              type="number"
              value={formData[field.previousKey] || ''}
              onChange={(e) => handleChange(field.previousKey, e.target.value)}
              placeholder={field.placeholder.previous}
              disabled={isLoading}
              style={{
                width: '100%',
                padding: '8px 10px',
                border: '1px solid #ddd',
                borderRadius: '6px',
                fontSize: '0.9rem',
              }}
            />
            <span style={{ color: '#888', fontSize: '0.8rem', minWidth: '30px' }}>万円</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
            <input
              type="number"
              value={formData[field.currentKey] || ''}
              onChange={(e) => handleChange(field.currentKey, e.target.value)}
              placeholder={field.placeholder.current}
              disabled={isLoading}
              style={{
                width: '100%',
                padding: '8px 10px',
                border: '1px solid #ddd',
                borderRadius: '6px',
                fontSize: '0.9rem',
              }}
            />
            <span style={{ color: '#888', fontSize: '0.8rem', minWidth: '30px' }}>万円</span>
          </div>
        </div>
      ))}

      {/* ボタン */}
      <div style={{
        display: 'flex',
        gap: '12px',
        marginTop: '16px',
      }}>
        <button
          onClick={handleSubmit}
          disabled={isLoading}
          style={{
            padding: '10px 24px',
            backgroundColor: '#4CAF50',
            color: 'white',
            border: 'none',
            borderRadius: '6px',
            fontSize: '0.95rem',
            cursor: isLoading ? 'not-allowed' : 'pointer',
            opacity: isLoading ? 0.7 : 1,
          }}
        >
          {isLoading ? '計算中...' : '試算する'}
        </button>
        <button
          onClick={onSkip}
          disabled={isLoading}
          style={{
            padding: '10px 24px',
            backgroundColor: 'transparent',
            color: '#666',
            border: '1px solid #ccc',
            borderRadius: '6px',
            fontSize: '0.95rem',
            cursor: isLoading ? 'not-allowed' : 'pointer',
          }}
        >
          スキップ
        </button>
      </div>
    </div>
  )
}

export default InlineCostForm

