import SharedHeader from '../components/SharedHeader'

export default function DashboardPage({ member, onSwitchToAgent, onSwitchToStore, onSwitchToDashboard }) {
  return (
    <div className="dashboard-page">
      <SharedHeader
        activePage="dashboard"
        member={member}
        onSwitchToAgent={() => onSwitchToAgent(null)}
        onSwitchToStore={onSwitchToStore}
        onSwitchToDashboard={onSwitchToDashboard}
      />
      <iframe
        className="dashboard-frame"
        src="/dashboard"
        title="Live Analytics Dashboard"
        allowFullScreen
      />
    </div>
  )
}
