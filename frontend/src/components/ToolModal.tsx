/**
 * 汎用ツールモーダルコンポーネント
 * 
 * モーダル設定に基づいて動的にフォームを生成し、
 * 入力データをバックエンドに送信します。
 */

import { useState, useEffect } from 'react'
import { ModalConfig, FieldConfig } from '../config/modal-config'

interface ToolModalProps {
  config: ModalConfig
  isOpen: boolean
  onClose: () => void
  onSubmit: (data: Record<string, number | string>) => void
  isLoading?: boolean
}

// フィールド入力コンポーネント
const FormField = ({
  field,
  value,
  onChange,
  disabled,
}: {
  field: FieldConfig
  value: string
  onChange: (value: string) => void
  disabled: boolean
}) => {
  const inputId = `field-${field.id}`

  return (
    <div className="form-group">
      <label htmlFor={inputId}>
        {field.label}
        {field.required && <span style={{ color: '#e74c3c', marginLeft: '4px' }}>*</span>}
      </label>
      <div style={{ position: 'relative' }}>
        {field.type === 'select' ? (
          <select
            id={inputId}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            className="form-input"
            disabled={disabled}
          >
            <option value="">選択してください</option>
            {field.options?.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <input
              id={inputId}
              type={field.type === 'number' || field.type === 'percentage' ? 'number' : 'text'}
              value={value}
              onChange={(e) => onChange(e.target.value)}
              placeholder={field.placeholder}
              className="form-input"
              disabled={disabled}
              style={{ flex: 1 }}
            />
            {field.suffix && (
              <span style={{ 
                color: '#666', 
                fontSize: '0.9rem',
                minWidth: '30px',
              }}>
                {field.suffix}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export const ToolModal = ({
  config,
  isOpen,
  onClose,
  onSubmit,
  isLoading = false,
}: ToolModalProps) => {
  // フォームデータの状態
  const [formData, setFormData] = useState<Record<string, string>>({})
  const [errors, setErrors] = useState<string[]>([])

  // モーダルが開いたときにフォームをリセット
  useEffect(() => {
    if (isOpen) {
      const initialData: Record<string, string> = {}
      config.fields.forEach((field) => {
        initialData[field.id] = field.defaultValue?.toString() ?? ''
      })
      setFormData(initialData)
      setErrors([])
    }
  }, [isOpen, config])

  // フィールド値の更新
  const handleFieldChange = (fieldId: string, value: string) => {
    setFormData((prev) => ({ ...prev, [fieldId]: value }))
  }

  // バリデーション
  const validate = (): boolean => {
    const newErrors: string[] = []
    
    config.fields.forEach((field) => {
      const value = formData[field.id]
      
      if (field.required && (!value || value.trim() === '')) {
        newErrors.push(`${field.label}を入力してください`)
      }
      
      if (value && (field.type === 'number' || field.type === 'percentage')) {
        const numValue = parseFloat(value)
        if (isNaN(numValue)) {
          newErrors.push(`${field.label}は数値で入力してください`)
        }
      }
    })

    setErrors(newErrors)
    return newErrors.length === 0
  }

  // 送信処理
  const handleSubmit = () => {
    if (!validate()) {
      return
    }

    // 数値フィールドを変換
    const processedData: Record<string, number | string> = {}
    config.fields.forEach((field) => {
      const value = formData[field.id]
      if (field.type === 'number' || field.type === 'percentage') {
        processedData[field.id] = parseFloat(value) || 0
      } else {
        processedData[field.id] = value
      }
    })

    onSubmit(processedData)
  }

  // グループごとにフィールドを分類
  const getFieldsByGroup = () => {
    if (!config.groups) {
      return [{ id: 'default', title: '', fields: config.fields }]
    }

    return config.groups.map((group) => ({
      ...group,
      fields: config.fields.filter((f) => f.group === group.id),
    }))
  }

  if (!isOpen) return null

  return (
    <div 
      className="modal-overlay" 
      onClick={() => !isLoading && onClose()}
    >
      <div 
        className="modal-content" 
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: '700px' }}
      >
        <h2>{config.title}</h2>
        <p className="modal-description">{config.description}</p>

        {/* エラー表示 */}
        {errors.length > 0 && (
          <div style={{
            backgroundColor: '#fee',
            border: '1px solid #e74c3c',
            borderRadius: '8px',
            padding: '12px',
            marginBottom: '1rem',
          }}>
            {errors.map((error, idx) => (
              <div key={idx} style={{ color: '#c0392b', fontSize: '0.9rem' }}>
                ⚠️ {error}
              </div>
            ))}
          </div>
        )}

        {/* フォームフィールド（グループ別） */}
        {getFieldsByGroup().map((group) => (
          <div key={group.id} style={{ marginBottom: '1.5rem' }}>
            {group.title && (
              <h3 style={{
                fontSize: '1.1rem',
                marginBottom: '1rem',
                borderBottom: '2px solid #e0e0e0',
                paddingBottom: '0.5rem',
                color: '#333',
              }}>
                {group.title}
              </h3>
            )}
            {group.fields.map((field) => (
              <FormField
                key={field.id}
                field={field}
                value={formData[field.id] || ''}
                onChange={(value) => handleFieldChange(field.id, value)}
                disabled={isLoading}
              />
            ))}
          </div>
        ))}

        {/* ボタン */}
        <div className="modal-buttons">
          <button
            onClick={handleSubmit}
            className="submit-button"
            disabled={isLoading}
          >
            {isLoading ? '処理中...' : config.submitLabel}
          </button>
          <button
            onClick={onClose}
            className="skip-button"
            disabled={isLoading}
            style={{
              padding: '0.875rem 2rem',
              backgroundColor: 'transparent',
              color: '#666666',
              border: '1px solid #d8d8d8',
              borderRadius: '8px',
              cursor: isLoading ? 'not-allowed' : 'pointer',
              fontSize: '0.9375rem',
              fontFamily: 'inherit',
            }}
          >
            キャンセル
          </button>
        </div>
      </div>
    </div>
  )
}

export default ToolModal



