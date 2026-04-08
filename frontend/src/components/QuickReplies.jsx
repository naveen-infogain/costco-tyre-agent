export default function QuickReplies({ replies, used, onSend }) {
  return (
    <div className="ta-quick-replies">
      {replies.map((reply, i) => (
        <button
          key={i}
          className={`ta-qr-chip${used ? ' used' : ''}`}
          onClick={() => !used && onSend(reply.message)}
        >
          {reply.label}
        </button>
      ))}
    </div>
  )
}
