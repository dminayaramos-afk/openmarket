import { useParams } from 'react-router-dom'
import { useAsync } from '../hooks'
import { api } from '../api'
import { Loading, Pill } from '../components/ui'

export default function ComingSoon() {
  const { id } = useParams()
  const mods = useAsync(() => api.modules(), [])
  if (mods.loading) return <Loading />
  const m = mods.data?.modules.find((x) => x.id === id)
  return (
    <div className="card p-8 max-w-xl">
      <h1 className="text-xl font-semibold mb-2">{m?.label ?? 'Sección'} <Pill tone="flat">en desarrollo</Pill></h1>
      <p className="text-sm text-muted">Esta sección todavía no está implementada. OpenMarket no muestra funciones simuladas ni datos de ejemplo disfrazados de reales: aparecerá aquí cuando exista una versión funcional y verificable.</p>
    </div>
  )
}
