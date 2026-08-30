import Hero13 from '@/components/ui/hero-13';

export default function Home() {
  return (
    <Hero13
      brandName="recall"
      navLinks={[
        { label: 'Platform', href: '#' },
        { label: 'Pricing', href: '#' },
        { label: 'Docs', href: '#' },
      ]}
      loginLabel="Auth"
      loginHref="/auth"
      badgeText="AI retrieval, deployed fast"
      headingLine1="Ship Retrieval"
      headingLine2="Without Friction."
      description="Stand up private knowledge search, ingestion, and chat flows without building the plumbing from scratch."
      primaryCtaLabel="Create account"
      primaryCtaHref="/auth"
      secondaryCtaLabel="Open auth"
      secondaryCtaHref="/auth"
      achievementText="Teams use recall to launch internal AI tools in days, not quarters"
    />
  );
}
