import { useEffect, useRef } from 'react'
import { useVoice } from '../hooks/useVoice'
import SharedHeader from '../components/SharedHeader'
import ChatFeed from '../components/ChatFeed'
import ChatInput from '../components/ChatInput'

export default function AgentPage({ member, onSwitchToStore, onSwitchToAgent, onSwitchToDashboard, initialVehicle, chatState }) {
  const {
    sessionId, messages, stage, isTyping,
    lastBotText, sendMessage, sendImage, sendFeedback, goBackToRecs,
  } = chatState

  const { voiceEnabled, isListening, isTtsPlaying, toggleMic, speakLastResponse } =
    useVoice(sendMessage, lastBotText, sessionId)

  const vehicleSentRef = useRef(false)

  useEffect(() => {
    if (initialVehicle && !vehicleSentRef.current) {
      vehicleSentRef.current = true
      setTimeout(() => sendMessage(`I'm looking for tyres for a ${initialVehicle}`), 400)
    }
  }, [initialVehicle]) // eslint-disable-line

  return (
    <div className="agent-page">
      <SharedHeader
        activePage="agent"
        stage={stage}
        member={member}
        onSwitchToAgent={onSwitchToAgent}
        onSwitchToStore={onSwitchToStore}
        onSwitchToDashboard={onSwitchToDashboard}
      />

      <div className="agent-bg">
        <div className="agent-card">

          {/* Title — full on empty state, compact single-line once chat starts */}
          <div className={`agent-card-title-wrap${messages.length > 0 ? ' compact' : ''}`}>
            <h1 className="agent-card-title">
              {messages.length > 0
                ? 'Meet TireAssist, Your AI Executive Assistant'
                : <> Meet TireAssist,<br />Your AI Executive Assistant </>
              }
            </h1>
          </div>

          {/* Messages */}
          <ChatFeed
            messages={messages}
            isTyping={isTyping}
            onSendMessage={sendMessage}
            onFeedback={sendFeedback}
            onBackToRecs={goBackToRecs}
          />

          {/* Input */}
          <ChatInput
            onSend={sendMessage}
            onSendImage={sendImage}
            isTyping={isTyping}
            voiceEnabled={voiceEnabled}
            isListening={isListening}
            isTtsPlaying={isTtsPlaying}
            onToggleMic={toggleMic}
            onTts={speakLastResponse}
          />

        </div>
      </div>
    </div>
  )
}
