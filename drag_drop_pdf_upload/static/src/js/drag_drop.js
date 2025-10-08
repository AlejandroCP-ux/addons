odoo.define("drag_drop_pdf_upload.drag_drop", function (require) {
  const FormRenderer = require("web.FormRenderer")
  console.log("âœ… drag_drop.js cargado correctamente");
  FormRenderer.include({
    _render: function () {
      const $el = this._super.apply(this, arguments)

      if (this.state.model === "firma.documento.wizard") {
        console.log("Wizard detectado: firma.documento.wizard")

        setTimeout(() => {
          const dropzone = $el.find(".o_drag_drop_zone")

          if (!dropzone.length) {
            console.warn("Dropzone no encontrada en el DOM.")
            return
          }

          console.log("âœ… Dropzone encontrada. Activando eventos...")

          dropzone.on("dragover", function (e) {
            e.preventDefault()
            dropzone.addClass("dragover")
            console.log("dragover detectado")
          })

          dropzone.on("dragleave", function () {
            dropzone.removeClass("dragover")
            console.log(" dragleave detectado")
          })

          dropzone.on("drop", function (e) {
            e.preventDefault()
            dropzone.removeClass("dragover")
            console.log("drop detectado")

            const files = e.originalEvent.dataTransfer.files
            console.log("Archivos recibidos:", files)

            if (!files.length) {
              alert("No se detectaron archivos.")
              return
            }

            for (const file of files) {
              console.log("Procesando archivo:", file.name, file.type)

              if (file.type !== "application/pdf") {
                alert("Solo se permiten archivos PDF. Archivo ignorado: " + file.name)
                continue
              }

              const reader = new FileReader()
              reader.onload = function (event) {
                const base64 = event.target.result.split(",")[1]

                const newRecord = {
                  document_name: file.name,
                  pdf_document: base64,
                }

                console.log("Enviando archivo al wizard:", newRecord)

                this.trigger_up("field_changed", {
                  dataPointID: this.state.id,
                  changes: {
                    document_ids: [...this.state.data.document_ids, newRecord],
                  },
                })

                alert("Archivo agregado: " + file.name)
              }.bind(this)

              reader.onerror = function () {
                console.error("Error al leer el archivo:", file.name)
                alert("Error al leer el archivo: " + file.name)
              }

              reader.readAsDataURL(file)
            }
          }.bind(this))
        }, 300) // Espera para asegurar que el DOM estÃ© listo
      }

      return $el
    },
  })
})
