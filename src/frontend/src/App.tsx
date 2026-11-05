import { Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { AssistantPage } from './features/assistant/AssistantPage'
import { RunDetailPage } from './features/assistant/RunDetailPage'
import { ProfilePage } from './features/profile/ProfilePage'
import { AuthPage } from './features/auth/AuthPage'
import { useMe } from './features/auth/queries'
import { SummaryPage } from './features/budget/SummaryPage'
import { ImportPage } from './features/import/ImportPage'
import { TransactionsPage } from './features/transactions/TransactionsPage'
import { pl } from './i18n/pl'

function Guard() {
  const me = useMe()
  if (me.isLoading) return <p className="p-6">{pl.common.loading}</p>
  if (!me.data) return <Navigate to="/login" replace />
  return <Layout email={me.data.email} />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<AuthPage mode="login" />} />
      <Route path="/register" element={<AuthPage mode="register" />} />
      <Route element={<Guard />}>
        <Route path="/" element={<SummaryPage />} />
        <Route path="/transactions" element={<TransactionsPage />} />
        <Route path="/import" element={<ImportPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/assistant" element={<AssistantPage />} />
        <Route path="/assistant/runs/:id" element={<RunDetailPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
