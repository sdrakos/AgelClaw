import { useState } from 'react'
import SkillCard from '../components/SkillCard'
import skills from '../data/skills.json'

const categories = ['All', ...Array.from(new Set(skills.map(s => s.category)))]

function SkillsPage() {
  const [activeCategory, setActiveCategory] = useState('All')

  const filtered = activeCategory === 'All'
    ? skills
    : skills.filter(s => s.category === activeCategory)

  return (
    <section className="pt-28 pb-24">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-3xl sm:text-4xl font-bold text-white mb-4">
            Skills Marketplace
          </h1>
          <p className="text-lg text-gray-400 max-w-2xl mx-auto">
            Browse and download skills to extend your agent. Free skills included with every installation.
          </p>
        </div>

        {/* Category filter */}
        <div className="flex flex-wrap justify-center gap-2 mb-10">
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setActiveCategory(cat)}
              className={`px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                activeCategory === cat
                  ? 'bg-indigo-600 text-white'
                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-200 border border-gray-700'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>

        {/* Skills grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((skill) => (
            <SkillCard key={skill.id} skill={skill} />
          ))}
        </div>

        {/* Count */}
        <p className="text-center mt-8 text-sm text-gray-500">
          Showing {filtered.length} of {skills.length} skills
        </p>
      </div>
    </section>
  )
}

export default SkillsPage
