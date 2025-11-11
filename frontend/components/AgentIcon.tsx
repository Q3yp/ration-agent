interface AgentIconProps {
  className?: string
  size?: number
}

export default function AgentIcon({ className = '', size = 24 }: AgentIconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      {/* Beaker/Flask body */}
      <path
        d="M9 2v6.5L5.5 14c-.5.9-.5 2 0 2.8.4.8 1.2 1.2 2 1.2h9c.8 0 1.6-.4 2-1.2.5-.8.5-1.9 0-2.8L15 8.5V2"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />

      {/* Flask opening */}
      <path
        d="M9 2h6"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />

      {/* Liquid level with bubbles effect */}
      <path
        d="M7 14h10"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        opacity="0.6"
      />

      {/* Small bubble 1 */}
      <circle
        cx="10"
        cy="12"
        r="1"
        fill="currentColor"
        opacity="0.4"
      />

      {/* Small bubble 2 */}
      <circle
        cx="14"
        cy="13"
        r="0.8"
        fill="currentColor"
        opacity="0.5"
      />

      {/* Small bubble 3 */}
      <circle
        cx="11.5"
        cy="15"
        r="0.6"
        fill="currentColor"
        opacity="0.3"
      />

      {/* DNA helix strand (left) */}
      <path
        d="M8 20c.5-.5.5-1 0-1.5"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
        opacity="0.7"
      />

      {/* DNA helix strand (right) */}
      <path
        d="M16 20c-.5-.5-.5-1 0-1.5"
        stroke="currentColor"
        strokeWidth="1.2"
        strokeLinecap="round"
        opacity="0.7"
      />

      {/* Connecting line between DNA strands */}
      <path
        d="M8.5 19.5h7"
        stroke="currentColor"
        strokeWidth="0.8"
        strokeLinecap="round"
        opacity="0.5"
      />
    </svg>
  )
}
