import { useState, useEffect } from 'react';

interface Skill {
  status: 'ready' | 'missing';
  icon: string;
  name: string;
  description: string;
  source: string;
}

function SkillsPage() {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/skills')
      .then((r) => r.json())
      .then((data) => {
        if (Array.isArray(data)) setSkills(data);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-5xl mx-auto">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">Agent Skills</h1>
        <p className="text-sm text-gray-500 mb-6">
          {loading ? 'Loading skills...' : `${skills.length} skills installed in your agent`}
        </p>

        {loading ? (
          <div className="text-center text-gray-400 py-12">Loading...</div>
        ) : skills.length === 0 ? (
          <div className="text-center text-gray-400 py-12">
            No skills found. Create one with <code className="bg-gray-100 px-1 rounded">python mem_cli.py create_skill</code>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {skills.map((skill) => (
              <div
                key={skill.name}
                className="bg-white rounded-xl border border-green-200 p-4 transition-shadow hover:shadow-md"
              >
                <div className="flex items-start gap-3">
                  <span className="text-2xl">{skill.icon}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="font-semibold text-gray-900 text-sm truncate">{skill.name}</h3>
                      <span className="inline-flex px-2 py-0.5 rounded-full text-[10px] font-medium bg-green-100 text-green-700">
                        ready
                      </span>
                    </div>
                    <p className="text-xs text-gray-500 leading-relaxed line-clamp-3">
                      {skill.description}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default SkillsPage;
