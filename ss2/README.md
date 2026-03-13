C:\Users\germa\Documents\NEOLAB\Project_1\neolab-docs>npm run dev


Próximo paso lógico

Cuando quieras, seguimos con:

📱 WhatsApp (Twilio / WATI / Cloud API)

🧠 Prioridad de alertas (urgente / hoy / próximo)

📊 Panel “Alertas enviadas”

🔁 Reintentos si falla el email

👥 Configuración por usuario (activar/desactivar canales)

Decime “seguimos con WhatsApp” o “mejoras de alertas” y avanzamos.

Crear eventos de alerta en Google calendar para que durante una semana antes de los vencimientos aparezca el aviso de alerta?

A) dejar el email más lindo (HTML con tabla + “Ver documento” link directo)

B) agregar WhatsApp (Twilio/WATI/Gupshup)

C) panel “Alertas enviadas” real (filtrar por status='enviada' + sent_at)



Agregar recuperación de contraseña para usuarios que olviden sus credenciales

Mejorar el diseño de la página de autenticación con animaciones y transiciones suaves

Agregar validación de email para verificar que el usuario sea real antes de activar la cuenta

Agregar vista previa del PDF dentro de la aplicación para ver el documento sin descargarlo.

Agregar edición manual de los datos extraídos del documento en caso de que la IA no los detecte correctamente.


Te propongo mejoras en orden de impacto (las 6 primeras te dejan el sistema “pro”) y después las “nice to have”.

1) Guardar bien el archivo: no guardes el signed URL en la tabla

Hoy estás guardando file_url como signed URL (vence). Mejor:

En documents guardá:

storage_bucket = 'documents'

storage_path = '${userId}/...pdf'

Cuando el frontend necesita ver/descargar, pedís un signed URL on-demand (o endpoint /api/documents/:id/signed-url).

✅ Evitás links vencidos y “documentos que desaparecen”.

2) Alertas de vencimiento reales (upcoming/overdue) + auto-creación

Dos cosas:

A) Normalizar estados (ahora mismo)

Tu UI estaba usando upcoming/overdue pero tu DB pendiente/enviada/cancelada.
Te conviene:

mantener DB: pendiente/enviada/cancelada

calcular “upcoming/overdue” en runtime según alert_date vs hoy, o agregar una vista.

B) Auto-crear alertas al procesar un doc

En tu route.ts, si due_date existe:

crear 3 alerts automáticamente: -7, -3, 0 días (o según settings del usuario)

setear alert_type='vencimiento'

3) Job diario que manda emails (y después WhatsApp)

Siguiente gran paso: “no es solo registro, también te avisa”.

Opción simple:

Vercel Cron (si deployás en Vercel)

Endpoint /api/cron/send-alerts

Query: alerts pendiente con alert_date = today

Enviar email (Resend / SendGrid) y marcar sent_at, status='enviada'

Luego sumamos WhatsApp (Twilio / WATI / Gupshup).

4) Procesamiento robusto: validación + retries + “confidence”

Ahora estás aceptando cualquier JSON. Mejoras:

Validar con zod antes de guardar:

moneda solo ARS|USD

total número positivo o null

fechas YYYY-MM-DD o null

Si falla validación:

reintentar con prompt “corregí el JSON”

Guardar confidence_score estimado (aunque sea simple):

si encontró total + due_date + issuer → alta

si faltan 2+ campos → media/baja

✅ baja muchísimo los “datos raros”.

5) Soporte para PDFs escaneados (OCR)

Hoy funciona perfecto en PDFs digitales. Para escaneados:

Detectar si extractTextFromPdfBytes() devuelve texto muy corto (ej < 50 chars)

En ese caso:

pasar a OCR (opciones top):

Google Document AI (muy bueno para facturas)

AWS Textract

Mindee (simple y fuerte)

LlamaParse (ya lo probaste en otros flujos)

✅ Esto te convierte el MVP en “casi universal”.

6) UX: progreso real + detalle del resultado

En el modal de upload:

mostrar “Subiendo / Extrayendo texto / Analizando / Guardando”

al terminar, mostrar un panel:

Tipo, Emisor, Total, Vencimiento

Botón “Editar” (por si OpenAI erró)

Y en la lista:

filtros: tipo, estado, vencimiento

orden por “más próximo a vencer”

Extras recomendados (cuando quieras)

Async mode opcional (para PDFs grandes): sube → status “procesando” → polling.

Dedupe por sha256 (evita subir 2 veces el mismo PDF).

Auditoría: guardar raw_text_excerpt (primeros 3k chars) para debug sin guardar todo.

Seguridad: no uses Service Role para lecturas normales; solo server-side y mínimo necesario.


cuando quiero logearme con Google:
{"code":400,"error_code":"validation_failed","msg":"Unsupported provider: provider is not enabled"}

Las políticas RLS requieren que auth.uid() = user_id. El problema es que UploadView.tsx no envía el user_id al insertar. Voy a corregir esto y también mejorar el procesamiento de PDFs usando el modelo más potente de Lovable AI:

Las políticas RLS requieren que auth.uid() = user_id. El problema es que UploadView.tsx no envía el user_id al insertar. Voy a corregir esto y también mejorar el procesamiento de PDFs usando el modelo más potente de Lovable AI:

Show all
1 edit made
Veo que el edge function usa gemini-2.5-flash. Para mejorar la extracción voy a:

Usar gemini-2.5-pro (más preciso para documentos complejos)
Mejorar el prompt para documentos argentinos (AFIP, etc.)
Agregar más robustez en el parsing
Veo que el edge function usa gemini-2.5-flash. Para mejorar la extracción voy a:

Usar gemini-2.5-pro (más preciso para documentos complejos)
Mejorar el prompt para documentos argentinos (AFIP, etc.)
Agregar más robustez en el parsing
Show all
1 edit made
Se corrigieron ambos problemas:

Error de RLS: UploadView.tsx ahora incluye el user_id del usuario autenticado al crear documentos
Mejora en extracción AI:
Actualizado a gemini-2.5-pro (modelo más preciso)
Agregados tipos: impuesto, servicio
Mejor manejo de montos argentinos (1.234,56)
Soporte para formatos de fecha argentinos (DD/MM/YYYY)
Más robusto con fallbacks ante errores de parsing