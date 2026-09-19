import MarketingPage from '@/components/marketing-page';

export default function AboutPage() {
  return (
    <MarketingPage
      eyebrow="About"
      title="Built for useful AI systems."
      description="Recall helps teams ship grounded retrieval experiences without spending months on infrastructure."
      rows={[
        { label: 'Focus', detail: 'Reduce the plumbing required to build private knowledge search.' },
        { label: 'Approach', detail: 'Keep source context close to every generated answer.' },
        { label: 'Goal', detail: 'Make production-ready RAG feel straightforward for small teams.' },
      ]}
    />
  );
}
