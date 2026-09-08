const navLinkClass = (active) =>
  `block rounded-lg px-3 py-2 text-sm transition ${
    active
      ? 'bg-brand-50 font-medium text-brand-700'
      : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
  }`

export default function CategorySidebar({ categories, active, onSelect }) {
  return (
    <nav className="w-full shrink-0 sm:w-44">
      <p className="px-3 text-xs font-medium uppercase tracking-wide text-gray-400">
        Shop by category
      </p>
      <div className="mt-2 flex gap-1 overflow-x-auto sm:flex-col sm:overflow-visible">
        <button onClick={() => onSelect(null)} className={navLinkClass(active === null)}>
          All items
        </button>
        {categories.map((c) => (
          <button key={c} onClick={() => onSelect(c)} className={navLinkClass(active === c)}>
            {c}
          </button>
        ))}
      </div>
    </nav>
  )
}
