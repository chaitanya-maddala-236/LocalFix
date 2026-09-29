import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from 'react'

export function Button({ variant = 'secondary', size = '', className = '', children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'ghost' | 'danger'; size?: 'small' | 'large' | ''; className?: string }) {
  return <button className={`button button-${variant} ${size ? `button-${size}` : ''} ${className}`} {...props}>{children}</button>
}

export function Badge({ children, tone = 'neutral', className = '' }: { children: ReactNode; tone?: 'neutral' | 'lime' | 'amber' | 'red' | 'blue'; className?: string }) {
  return <span className={`badge badge-${tone} ${className}`}>{children}</span>
}

export function Card({ children, className = '', ...props }: HTMLAttributes<HTMLElement>) {
  return <section className={`card ${className}`} {...props}>{children}</section>
}

export function PageHeading({ eyebrow, title, subtitle, action }: { eyebrow: string; title: ReactNode; subtitle?: string; action?: ReactNode }) {
  return <div className="page-heading"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1>{subtitle && <p>{subtitle}</p>}</div>{action && <div className="heading-action">{action}</div>}</div>
}

export function SectionTitle({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return <div className="section-title"><h2>{children}</h2>{action}</div>
}
