const PATHS = {
  menu: <><path d="M4 7h16M4 12h16M4 17h16" /></>,
  plus: <path d="M12 5v14M5 12h14" />,
  search: <><circle cx="10.8" cy="10.8" r="5.8" /><path d="m16 16 4 4" /></>,
  sliders: <><path d="M4 6h16M4 12h16M4 18h16" /><circle cx="9" cy="6" r="1.8" fill="currentColor" stroke="none" /><circle cx="15" cy="12" r="1.8" fill="currentColor" stroke="none" /><circle cx="11" cy="18" r="1.8" fill="currentColor" stroke="none" /></>,
  panel: <><rect x="4" y="4" width="16" height="16" rx="2" /><path d="M9 4v16" /></>,
  folder: <path d="M3.5 7.5h6l1.7 2H20.5v8.8a1.7 1.7 0 0 1-1.7 1.7H5.2a1.7 1.7 0 0 1-1.7-1.7zM3.5 7.5V6a1.5 1.5 0 0 1 1.5-1.5h4l1.7 2h7.8A2 2 0 0 1 20.5 8v1.5" />,
  settings: <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1-1.8 1.8-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5v.2h-2.6v-.2a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.9.3l-.1.1-1.8-1.8.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H6.3v-2.6h.2a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.9l-.1-.1 1.8-1.8.1.1a1.7 1.7 0 0 0 1.9.3 1.7 1.7 0 0 0 1-1.5v-.2H15v.2a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1 1.8 1.8-.1.1a1.7 1.7 0 0 0-.3 1.9 1.7 1.7 0 0 0 1.5 1h.2V14h-.2a1.7 1.7 0 0 0-1.5 1z" /></>,
  arrow: <><path d="M5 12h14" /><path d="m13 6 6 6-6 6" /></>,
  chevronDown: <path d="m7 9 5 5 5-5" />,
  workspace: <><circle cx="12" cy="12" r="7" /><path d="M12 8v8M8 12h8" /></>,
  send: <path d="M12 19V5M6 11l6-6 6 6" />,
}

export default function Icon({ name, size = 16, className = '' }) {
  return (
    <svg
      className={`ui-icon ${className}`}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {PATHS[name]}
    </svg>
  )
}
