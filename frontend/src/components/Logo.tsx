import React from 'react';

interface LogoProps {
  collapsed?: boolean;
}

const Logo: React.FC<LogoProps> = ({ collapsed = false }) => {
  if (collapsed) {
    // Collapsed: show stylized X only, centered
    return (
      <svg width="36" height="36" viewBox="0 0 36 36" fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="xGradC" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#06b6d4" />
            <stop offset="100%" stopColor="#0d9488" />
          </linearGradient>
          <filter id="glowC" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="1.5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>
        {/* X shape — two crossed bars with pointed ends */}
        <g filter="url(#glowC)">
          <path
            d="M7 5 L16 15 L7 31 L11 31 L18 19.5 L25 31 L29 31 L20 15 L29 5 L25 5 L18 14.5 L11 5 Z"
            fill="url(#xGradC)"
          />
          {/* Small diamond accent at center */}
          <rect x="15.5" y="13" width="5" height="5" rx="0.5" transform="rotate(45 18 15.5)" fill="#06b6d4" opacity="0.5" />
        </g>
      </svg>
    );
  }

  // Expanded: full "2mX" text logo, centered
  return (
    <svg width="120" height="42" viewBox="0 0 120 42" fill="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="xGrad" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#06b6d4" />
          <stop offset="100%" stopColor="#0d9488" />
        </linearGradient>
        <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="2" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      {/* "2" — bold, modern numeral */}
      <text
        x="8"
        y="31"
        fontFamily="'Inter', 'Segoe UI', sans-serif"
        fontWeight="800"
        fontSize="30"
        fill="#e2e8f0"
        letterSpacing="-1"
      >
        2
      </text>

      {/* "m" — slightly lighter weight */}
      <text
        x="28"
        y="31"
        fontFamily="'Inter', 'Segoe UI', sans-serif"
        fontWeight="600"
        fontSize="28"
        fill="#94a3b8"
        letterSpacing="-0.5"
      >
        m
      </text>

      {/* Stylized "X" — geometric with gradient and glow */}
      <g filter="url(#glow)" transform="translate(64, 3)">
        <path
          d="M5 3 L15.5 16.5 L5 33 L10 33 L18.5 20 L27 33 L32 33 L21.5 16.5 L32 3 L27 3 L18.5 13.5 L10 3 Z"
          fill="url(#xGrad)"
        />
        {/* Diamond accent at crossover */}
        <rect x="16" y="12.5" width="5" height="5" rx="0.5" transform="rotate(45 18.5 15)" fill="#06b6d4" opacity="0.4" />
      </g>
    </svg>
  );
};

export default Logo;
