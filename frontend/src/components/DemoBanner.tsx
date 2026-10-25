interface Props {
  text?: string;
}

// Used on every page whose backend engine doesn't exist yet -- the numbers
// shown below this banner are static examples for layout preview only, never
// real market data. Keep this visible, not a one-time dismissible toast, so
// there's no way to forget which pages are real.
export function DemoBanner({ text }: Props) {
  return (
    <div className="demo-banner" role="note">
      <span className="demo-banner-tag">DEMO DATA</span>
      <span className="demo-banner-text">
        {text ?? "This page is not connected to live analysis yet. Everything below is a static example, not real market data."}
      </span>
    </div>
  );
}
