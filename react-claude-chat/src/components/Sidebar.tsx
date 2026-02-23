interface SidebarProps {
  activePage: string;
  onPageChange: (page: string) => void;
}

const sections = [
  {
    label: 'General',
    items: [
      { id: 'chat', icon: '💬', label: 'Chat' },
      { id: 'skills', icon: '⭐', label: 'Skills' },
    ],
  },
  {
    label: 'Settings',
    items: [
      { id: 'models', icon: '🤖', label: 'Models' },
    ],
  },
];

function Sidebar({ activePage, onPageChange }: SidebarProps) {
  return (
    <aside className="w-56 bg-gray-900 text-gray-300 flex-shrink-0 flex flex-col border-r border-gray-800">
      <div className="px-5 py-4 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-xs">A</span>
          </div>
          <span className="font-semibold text-white text-sm">Agel Agent</span>
        </div>
      </div>

      <nav className="flex-1 py-2 overflow-y-auto">
        {sections.map((section) => (
          <div key={section.label}>
            <div className="px-5 pt-4 pb-1 text-[10px] uppercase tracking-widest text-gray-500 font-medium">
              {section.label}
            </div>
            {section.items.map((item) => (
              <button
                key={item.id}
                onClick={() => onPageChange(item.id)}
                className={`w-full flex items-center gap-2.5 px-5 py-2 text-sm transition-colors ${
                  activePage === item.id
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-400 hover:bg-gray-800 hover:text-gray-200'
                }`}
              >
                <span className="text-base">{item.icon}</span>
                {item.label}
              </button>
            ))}
          </div>
        ))}
      </nav>
    </aside>
  );
}

export default Sidebar;
