interface ModelableGuideProps {
  title: string
  description: string
  models: string[]
  sourceHref: string
}

const MODELABLE_DOCS = 'https://ktjn.github.io/modelable/'

export function ModelableGuide({ title, description, models, sourceHref }: ModelableGuideProps) {
  return (
    <aside className="modelable-guide" aria-label="Modelable context">
      <div className="modelable-guide__copy">
        <span className="section-heading__kicker">Modelable in this view</span>
        <strong>{title}</strong>
        <p>{description}</p>
      </div>
      <div className="modelable-guide__contract" aria-label="Modelable contracts used">
        {models.map(model => <code key={model}>{model}</code>)}
      </div>
      <div className="modelable-guide__links">
        <a href={sourceHref}>Open model source</a>
        <a href={MODELABLE_DOCS}>Read the Modelable docs</a>
      </div>
    </aside>
  )
}
