export default function ImageBubble({ src, name }) {
  return (
    <div className="msg-row user">
      <div className="img-bubble">
        <img src={src} alt={name || 'Uploaded tyre image'} className="img-bubble-img" />
        <div className="img-bubble-caption">
          <span className="material-symbols-rounded" style={{ fontSize: 13 }}>image_search</span>
          Analysing tyre image…
        </div>
      </div>
    </div>
  )
}
