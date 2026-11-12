import type { pl } from '../../i18n/pl'
import type { AssetClass } from './queries'

export type FieldTextKey = keyof typeof pl.portfolio.fieldText

export type FieldKey =
  | 'symbol'
  | 'currency'
  | 'quantity'
  | 'purchase_price'
  | 'purchase_date'
  | 'manual_value'

export type FieldSpec = {
  key: FieldKey
  required?: boolean
  /** Key into pl.portfolio.fieldText; defaults to `key`. Lets a class reword a shared field. */
  text?: FieldTextKey
  placeholder?: string
}

export type ClassConfig = {
  fields: FieldSpec[]
  /** Values sent for fields that are not shown when CREATING (backend requires them). Edits keep the stored value. */
  fixed?: Partial<Record<FieldKey, string>>
  /** Quotes are fetched automatically (yfinance) when a symbol is given. */
  auto: boolean
}

const currency: FieldSpec = { key: 'currency', required: true }
const date: FieldSpec = { key: 'purchase_date' }

export const CLASS_CONFIG: Record<AssetClass, ClassConfig> = {
  stock: {
    auto: true,
    fields: [
      { key: 'symbol', required: true, placeholder: 'AAPL, CDR.WA' },
      currency,
      { key: 'quantity', required: true, placeholder: '10' },
      { key: 'purchase_price', required: true, placeholder: '100,00' },
      date,
    ],
  },
  etf: {
    auto: true,
    fields: [
      { key: 'symbol', required: true, placeholder: 'VWCE.DE, SPY' },
      currency,
      { key: 'quantity', required: true, placeholder: '10' },
      { key: 'purchase_price', required: true, placeholder: '100,00' },
      date,
    ],
  },
  crypto: {
    auto: true,
    fields: [
      { key: 'symbol', required: true, text: 'cryptoSymbol', placeholder: 'BTC, ETH' },
      { key: 'quantity', required: true, placeholder: '0,5' },
      { key: 'purchase_price', required: true, placeholder: '40000,00' },
      { ...currency, text: 'cryptoCurrency' },
      date,
    ],
  },
  commodity: {
    auto: true,
    fields: [
      { key: 'symbol', text: 'commoditySymbol', placeholder: 'GC=F' },
      currency,
      { key: 'quantity', required: true, placeholder: '2' },
      { key: 'purchase_price', required: true, placeholder: '8000,00' },
      date,
      { key: 'manual_value', text: 'manualValueOptional' },
    ],
  },
  bond: {
    auto: false,
    fields: [
      currency,
      { key: 'quantity', required: true, text: 'bondQuantity', placeholder: '100' },
      { key: 'purchase_price', required: true, text: 'bondPrice', placeholder: '100,00' },
      date,
      { key: 'manual_value', required: true, text: 'manualValueTotal' },
    ],
  },
  real_estate: {
    auto: false,
    fixed: { quantity: '1' },
    fields: [
      currency,
      { key: 'purchase_price', required: true, text: 'propertyPrice', placeholder: '400000,00' },
      date,
      { key: 'manual_value', text: 'manualValueTotal' },
    ],
  },
  cash: {
    auto: false,
    fixed: { quantity: '1' },
    fields: [
      currency,
      { key: 'purchase_price', required: true, text: 'cashAmount', placeholder: '10000,00' },
      date,
    ],
  },
}

export const FIELD_KEYS: FieldKey[] = [
  'symbol',
  'currency',
  'quantity',
  'purchase_price',
  'purchase_date',
  'manual_value',
]
