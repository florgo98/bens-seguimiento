# Seguimiento — Esteban & Dueños

Mini web app en Flask con la misma herramienta que ya venías usando
(checkboxes, niveles de riesgo 2-5, auto-escalado semanal, filtros,
deshacer), pero ahora con backend propio en vez de storage de Claude.
Así Esteban puede entrar desde su navegador y ver/editar la misma lista
que vos.

## Cómo correrlo local (opcional, para probar)

```bash
pip install -r requirements.txt
python app.py
```

Abrí `http://localhost:5000`.

## Deploy en Railway (mismo flujo que `auditoria-rvas-web`)

1. Creá un repo nuevo en GitHub y subí esta carpeta:
   ```bash
   git init
   git add .
   git commit -m "Seguimiento de dueños - primera versión"
   git branch -M main
   git remote add origin <URL_DE_TU_REPO>
   git push -u origin main
   ```
2. En Railway: **New Project → Deploy from GitHub repo** y elegí este repo.
3. Railway detecta el `Procfile` y lo levanta solo. No hace falta configurar
   nada más — la variable `PORT` la define Railway automáticamente.
4. Cuando termine el deploy, andá a **Settings → Networking → Generate Domain**
   para tener una URL pública (algo tipo `xxxx.up.railway.app`).
5. Pasále esa URL a Esteban. Cualquiera que entre ahí ve y edita la misma lista.

## Importante: persistencia de los datos

Los datos se guardan en un archivo `data.json` dentro del propio contenedor.
Mientras no borres el servicio o hagas un redeploy que reconstruya todo desde
cero, los datos quedan. Pero si querés que sobrevivan **sí o sí** a cualquier
redeploy (recomendado si esto va a ser de uso diario), agregale un Volume:

1. En Railway: **tu servicio → Settings → Volumes → New Volume**.
2. Mount path: `/data`
3. En **Variables**, agregá: `DATA_FILE=/data/data.json`
4. Redeploy. A partir de ahí, los datos viven en el volume y sobreviven
   a cualquier redeploy futuro.

Sin ese paso, igual funciona bien para uso normal — el volume es solo un
seguro extra contra pérdida de datos en un redeploy grande.

## Notas

- No tiene login: cualquiera con el link puede ver y editar. Para un equipo
  chico como este está bien, pero si más adelante lo compartís más ampliamente
  y querés restringir acceso, se le puede sumar una contraseña simple
  (Basic Auth) sin mucho trabajo — avisame y lo agrego.
- Si dos personas editan lo mismo casi al mismo tiempo, gana el último guardado
  (no hay fusión de cambios). Para el volumen de uso que le van a dar entre
  vos y Esteban no debería ser un problema real.
- La página se refresca sola cada 20 segundos para traer cambios del otro,
  sin pisar lo que estés escribiendo en ese momento.
