// Author: @yansha
//
// Description:
// Power switch based on Panasonic_EVQPUJ_EVQPUA
//
// Requires KiCad7.0 

module.exports = {
    params: {
      designator: 'SW',
      side: 'F',
      from: {type: 'net', value: 'BAT_P'},
      to: {type: 'net', value: 'RAW'},
      reverse: false,
      pads: 'smd' // through-hole
    },
    body: p => {
      const top = `
        (footprint "Button_Switch_SMD:Panasonic_EVQPUJ_EVQPUA" (layer "F.Cu")
        (tstamp 3abfcbf1-9783-438b-873a-0c0c06d35072)
          ${p.at /* parametric position */}
        (descr "http://industrial.panasonic.com/cdbs/www-data/pdf/ATV0000/ATV0000CE5.pdf")
        (tags "SMD SMT SPST EVQPUJ EVQPUA")
        (attr smd)
        (fp_text reference "${p.ref}" (at 0 -4.5 ${p.rot}) (layer "${p.side}.SilkS") ${p.ref_hide}
        (effects (font (size 1 1) (thickness 0.15)) ${p.side =="B" ? "(justify mirror)" : ""})
          (tstamp e0222d06-951a-47ac-a645-a99d80f35e6e)
        )
        (fp_text value "" (at 0 3.5 ${p.rot}) (layer "${p.side}.Fab")
            (effects (font (size 1 1) (thickness 0.15)))
          (tstamp a0b52c51-2769-4d6a-990f-8f9d27a96038)
        )
      `
        // Can add for consistency, but creates unneeded noise
        // (fp_text user "\${REFERENCE}" (at 0 0 ${p.rot}) (layer "${p.side}.Fab")
        //     (effects (font (size 1 1) (thickness 0.15)))
        //   (tstamp faa862a8-c285-4488-88f6-297bd545c95f)
        // )

      const front = `
        (fp_line (start -2.45 0.275) (end -2.45 -0.275) (stroke (width 0.12) (type solid)) (layer "F.SilkS") (tstamp f625b7e8-5e08-4fb1-baf0-96de402eb6b4))
        (fp_line (start -1.425 -1.85) (end -2.35 -1.85) (stroke (width 0.12) (type solid)) (layer "F.SilkS") (tstamp 0c91385e-e408-49ea-93b7-48996e281359))
        (fp_line (start 2.35 -1.85) (end 1.425 -1.85) (stroke (width 0.12) (type solid)) (layer "F.SilkS") (tstamp e71df457-0730-4ba6-a3b7-2370f82c271d))
        (fp_line (start 2.35 1.85) (end -2.35 1.85) (stroke (width 0.12) (type solid)) (layer "F.SilkS") (tstamp 2d63d05c-61c1-46c3-b42e-c51f13d9669c))
        (fp_line (start 2.45 0.275) (end 2.45 -0.275) (stroke (width 0.12) (type solid)) (layer "F.SilkS") (tstamp 5d3e1ea7-3bb3-445a-8960-361dc3121fd0))
        (fp_line (start -3.9 2.25) (end -3.9 -3.25) (stroke (width 0.05) (type solid)) (layer "F.CrtYd") (tstamp 43f76e4b-64fd-42f7-866d-1e8d0a337566))
        (fp_line (start 3.9 -3.25) (end -3.9 -3.25) (stroke (width 0.05) (type solid)) (layer "F.CrtYd") (tstamp a27fb084-5a55-4255-8b7d-0a66b2fa837f))
        (fp_line (start 3.9 2.25) (end -3.9 2.25) (stroke (width 0.05) (type solid)) (layer "F.CrtYd") (tstamp eca845d4-dbaa-4d6e-8d8e-af544ba3000e))
        (fp_line (start 3.9 2.25) (end 3.9 -3.25) (stroke (width 0.05) (type solid)) (layer "F.CrtYd") (tstamp 0e8f07df-cbdb-4977-8b3d-96391666b7b8))
        (fp_line (start -2.35 1.75) (end -2.35 -1.75) (stroke (width 0.1) (type solid)) (layer "F.Fab") (tstamp 3682423a-9da4-4f6c-bf4c-0f4b05819bf8))
        (fp_line (start -1.3 -2.75) (end -1.3 -1.75) (stroke (width 0.1) (type solid)) (layer "F.Fab") (tstamp 2a79735e-2a10-449e-bbc4-0f35996d9965))
        (fp_line (start 1.3 -2.75) (end -1.3 -2.75) (stroke (width 0.1) (type solid)) (layer "F.Fab") (tstamp f965ab5b-6272-46cc-9033-a535aa0b340a))
        (fp_line (start 1.3 -2.75) (end 1.3 -1.75) (stroke (width 0.1) (type solid)) (layer "F.Fab") (tstamp 61cf744b-9ebd-4e28-8696-d35b386d1c47))
        (fp_line (start 2.35 -1.75) (end -2.35 -1.75) (stroke (width 0.1) (type solid)) (layer "F.Fab") (tstamp 27631cb6-d84f-4e04-b0a5-a0586a4549b0))
        (fp_line (start 2.35 1.75) (end -2.35 1.75) (stroke (width 0.1) (type solid)) (layer "F.Fab") (tstamp 5457aa5b-300a-47d1-bae6-afe0af504242))
        (fp_line (start 2.35 1.75) (end 2.35 -1.75) (stroke (width 0.1) (type solid)) (layer "F.Fab") (tstamp c9829f68-1659-46f8-bf79-ed5613871e77))
        (model "\${KICAD6_3DMODEL_DIR}/Button_Switch_SMD.3dshapes/Panasonic_EVQPUJ_EVQPUA.wrl"
          (offset (xyz 0 0 0))
          (scale (xyz 1 1 1))
          (rotate (xyz 0 0 0))
        )
      `
      const back = `
        (fp_line (start -2.45 0.275) (end -2.45 -0.275) (stroke (width 0.12) (type solid)) (layer "B.SilkS") (tstamp f625b7e8-5e08-4fb1-baf0-96de402eb6b4))
        (fp_line (start -1.425 -1.85) (end -2.35 -1.85) (stroke (width 0.12) (type solid)) (layer "B.SilkS") (tstamp 0c91385e-e408-49ea-93b7-48996e281359))
        (fp_line (start 2.35 1.85) (end -2.35 1.85) (stroke (width 0.12) (type solid)) (layer "B.SilkS") (tstamp 2d63d05c-61c1-46c3-b42e-c51f13d9669c))
        (fp_line (start 2.35 -1.85) (end 1.425 -1.85) (stroke (width 0.12) (type solid)) (layer "B.SilkS") (tstamp e71df457-0730-4ba6-a3b7-2370f82c271d))
        (fp_line (start 2.45 0.275) (end 2.45 -0.275) (stroke (width 0.12) (type solid)) (layer "B.SilkS") (tstamp 5d3e1ea7-3bb3-445a-8960-361dc3121fd0))
        (fp_line (start -3.9 2.25) (end -3.9 -3.25) (stroke (width 0.05) (type solid)) (layer "B.CrtYd") (tstamp 43f76e4b-64fd-42f7-866d-1e8d0a337566))
        (fp_line (start 3.9 2.25) (end -3.9 2.25) (stroke (width 0.05) (type solid)) (layer "B.CrtYd") (tstamp eca845d4-dbaa-4d6e-8d8e-af544ba3000e))
        (fp_line (start 3.9 2.25) (end 3.9 -3.25) (stroke (width 0.05) (type solid)) (layer "B.CrtYd") (tstamp 0e8f07df-cbdb-4977-8b3d-96391666b7b8))
        (fp_line (start 3.9 -3.25) (end -3.9 -3.25) (stroke (width 0.05) (type solid)) (layer "B.CrtYd") (tstamp a27fb084-5a55-4255-8b7d-0a66b2fa837f))
        (fp_line (start -2.35 1.75) (end -2.35 -1.75) (stroke (width 0.1) (type solid)) (layer "B.Fab") (tstamp 3682423a-9da4-4f6c-bf4c-0f4b05819bf8))
        (fp_line (start -1.3 -2.75) (end -1.3 -1.75) (stroke (width 0.1) (type solid)) (layer "B.Fab") (tstamp 2a79735e-2a10-449e-bbc4-0f35996d9965))
        (fp_line (start 1.3 -2.75) (end -1.3 -2.75) (stroke (width 0.1) (type solid)) (layer "B.Fab") (tstamp f965ab5b-6272-46cc-9033-a535aa0b340a))
        (fp_line (start 1.3 -2.75) (end 1.3 -1.75) (stroke (width 0.1) (type solid)) (layer "B.Fab") (tstamp 61cf744b-9ebd-4e28-8696-d35b386d1c47))
        (fp_line (start 2.35 1.75) (end -2.35 1.75) (stroke (width 0.1) (type solid)) (layer "B.Fab") (tstamp 5457aa5b-300a-47d1-bae6-afe0af504242))
        (fp_line (start 2.35 1.75) (end 2.35 -1.75) (stroke (width 0.1) (type solid)) (layer "B.Fab") (tstamp c9829f68-1659-46f8-bf79-ed5613871e77))
        (fp_line (start 2.35 -1.75) (end -2.35 -1.75) (stroke (width 0.1) (type solid)) (layer "B.Fab") (tstamp 27631cb6-d84f-4e04-b0a5-a0586a4549b0))
        (model "\${KICAD6_3DMODEL_DIR}/Button_Switch_SMD.3dshapes/Panasonic_EVQPUJ_EVQPUA.wrl"
          (offset (xyz 0 0 0))
          (scale (xyz 1 1 1))
          (rotate (xyz 0 0 0))
        )
      `
      pads_smd_front =`
        (pad "1" smd rect (at -2.625 -0.85 ${180+p.rot}) (size 1.55 1) (layers "F.Cu" "F.Paste" "F.Mask") ${p.from.str} (tstamp f66be888-8ac9-4d3e-86bd-648a1c946922))
        (pad "1" smd rect (at 2.625 -0.85 ${180+p.rot}) (size 1.55 1) (layers "F.Cu" "F.Paste" "F.Mask") ${p.from.str} (tstamp fdaf375e-1ea4-4341-a4d3-a744fbe9d9ab))
        (pad "2" smd rect (at -2.625 0.85 ${180+p.rot}) (size 1.55 1) (layers "F.Cu" "F.Paste" "F.Mask") ${p.to.str} (tstamp 2c770693-5a8b-44d6-9829-990b48addbb3))
        (pad "2" smd rect (at 2.625 0.85 ${180+p.rot}) (size 1.55 1) (layers "F.Cu" "F.Paste" "F.Mask") ${p.to.str} (tstamp 40de67a0-689b-44fd-808f-3715ea4165c1))
      `

      pads_smd_back = `
        (pad "1" smd rect (at -2.625 0.85 ${p.rot}) (size 1.55 1) (layers "B.Cu" "B.Paste" "B.Mask") ${p.from.str} (tstamp f66be888-8ac9-4d3e-86bd-648a1c946922))
        (pad "1" smd rect (at 2.625 0.85 ${p.rot}) (size 1.55 1) (layers "B.Cu" "B.Paste" "B.Mask") ${p.from.str} (tstamp fdaf375e-1ea4-4341-a4d3-a744fbe9d9ab))
        (pad "2" smd rect (at -2.625 -0.85 ${p.rot}) (size 1.55 1) (layers "B.Cu" "B.Paste" "B.Mask") ${p.to.str} (tstamp 2c770693-5a8b-44d6-9829-990b48addbb3))
        (pad "2" smd rect (at 2.625 -0.85 ${p.rot}) (size 1.55 1) (layers "B.Cu" "B.Paste" "B.Mask") ${p.to.str} (tstamp 40de67a0-689b-44fd-808f-3715ea4165c1))
      `

      pads_through_hole = `
        (pad "1" thru_hole rect (at -2.625 0.85 ${p.rot}) (size 1.55 1) (drill 0.4) (layers "*.Cu" "*.Paste" "*.Mask") (remove_unused_layers) (keep_end_layers) (zone_layer_connections) ${p.from.str} (tstamp f66be888-8ac9-4d3e-86bd-648a1c946922))
        (pad "1" thru_hole rect (at 2.625 0.85 ${p.rot}) (size 1.55 1) (drill 0.4) (layers "*.Cu" "*.Paste" "*.Mask") (remove_unused_layers) (keep_end_layers) (zone_layer_connections) ${p.from.str} (tstamp fdaf375e-1ea4-4341-a4d3-a744fbe9d9ab))
        (pad "2" thru_hole rect (at -2.625 -0.85 ${p.rot}) (size 1.55 1) (drill 0.4) (layers "*.Cu" "*.Paste" "*.Mask") (remove_unused_layers) (keep_end_layers) (zone_layer_connections) ${p.to.str} (tstamp 2c770693-5a8b-44d6-9829-990b48addbb3))
        (pad "2" thru_hole rect (at 2.625 -0.85 ${p.rot}) (size 1.55 1) (drill 0.4) (layers "*.Cu" "*.Paste" "*.Mask") ${p.to.str} (remove_unused_layers) (keep_end_layers) (zone_layer_connections) (tstamp 40de67a0-689b-44fd-808f-3715ea4165c1))
      `

      const bottom = `
      ${'' /* Add parts that should be on both sides here (closing bracket) */}
      )
      `

      let final = top;

      if(p.side == "F" || p.reverse) {
        final += front;
      }
      if(p.side == "B" || p.reverse) {
        final += back;
      }

      if(p.pads =='through-hole') {
        final += pads_through_hole;
      } else {
        if(p.side == "F" || p.reverse) {
          final += pads_smd_front;
        }
        if(p.side == "B" || p.reverse) {
          final += pads_smd_back;
        }
      }

      final += bottom;

      return final;
    }
  }

