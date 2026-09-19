import MarketingPage from '@/components/marketing-page';

export default function PricingPage() {
  return (
    <MarketingPage
      eyebrow="Pricing"
      title="Simple plans that scale."
      description="Start small, then add documents, seats, and usage as your knowledge product grows."
      rows={[
        { label: 'Starter', detail: 'For prototypes and small internal tools.', value: '$19/mo' },
        { label: 'Team', detail: 'Shared workspaces, higher limits, and production usage.', value: '$99/mo' },
        { label: 'Business', detail: 'Advanced controls, priority support, and custom limits.', value: 'Custom' },
      ]}
    />
  );
}
