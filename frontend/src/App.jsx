import { useState } from 'react'
import { useChat } from './hooks/useChat'
import SignInPage from './pages/SignInPage'
import CostcoStorePage from './pages/CostcoStorePage'
import AgentPage from './pages/AgentPage'
import DashboardPage from './pages/DashboardPage'

export default function App() {
  const [page, setPage] = useState('signin')
  const [initialVehicle, setInitialVehicle] = useState(null)
  const [member, setMember] = useState(null)   // { id, name }
  const chatState = useChat()

  function handleSignInSuccess({ memberId, ...data }) {
    const nameMatch = data.message?.match(/(?:hey|hello|hi)[,\s]+([A-Z][a-z]+)/i)
    const name = nameMatch?.[1] || memberId
    setMember({ id: memberId, name })
    chatState.handleLoginResponse(data)
    setPage('store')
  }

  function switchToAgent(vehicleContext = null) {
    setInitialVehicle(vehicleContext)
    setPage('agent')
  }

  function switchToStore() {
    setInitialVehicle(null)
    setPage('store')
  }

  function switchToDashboard() {
    setPage('dashboard')
  }

  if (page === 'signin') {
    return (
      <SignInPage
        sessionId={chatState.sessionId}
        onSignInSuccess={handleSignInSuccess}
      />
    )
  }

  if (page === 'store') {
    return (
      <CostcoStorePage
        member={member}
        onSwitchToAgent={switchToAgent}
        onSwitchToStore={switchToStore}
        onSwitchToDashboard={switchToDashboard}
      />
    )
  }

  if (page === 'dashboard') {
    return (
      <DashboardPage
        member={member}
        onSwitchToAgent={switchToAgent}
        onSwitchToStore={switchToStore}
        onSwitchToDashboard={switchToDashboard}
      />
    )
  }

  return (
    <AgentPage
      member={member}
      onSwitchToStore={switchToStore}
      onSwitchToAgent={switchToAgent}
      onSwitchToDashboard={switchToDashboard}
      initialVehicle={initialVehicle}
      chatState={chatState}
    />
  )
}
