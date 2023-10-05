// Author: @infused-kim + @yanshay improvements
//
// Description:
// Let's you place solder pads on the PCB that can be used instead of
// connectors. Useful for batteries and other peripherals in case the end-user
// does not have the right cable connector.
//
// Fully reversible and pads are mirrored on the back side.
//
// Updates by #yanshay: 1. Renamed mirorr to mirror_nets because mirror parameter did not pass
//                      into footprint, probably due to it being reserved word in ergogen?
//                      Changing to mirorr_nets made it work
//                      2. Added smd_type and drill_size support for through-holes
// 
// @yanshay improvements:
// - Added pad_type & drill_size to specify throughhole type pad

module.exports = {
    params: {
        designator: 'PAD',
        side: 'F',
        reverse: true,
        width: 1.25,
        height: 2.5,
        space: 2,
        mirror_nets: true,
        pads: 2,
        pads_type: 'smd', // through-hole, // TODO: Add support for labels on both sides if through-hole is used
        drill_size: 0.4,
        net_1: {type: 'net', value: 'PAD_1'},
        net_2: {type: 'net', value: 'PAD_2'},
        net_3: {type: 'net', value: 'PAD_3'},
        net_4: {type: 'net', value: 'PAD_4'},
        net_5: {type: 'net', value: 'PAD_5'},
        net_6: {type: 'net', value: 'PAD_5'},
        label_1: '',
        label_2: '',
        label_3: '',
        label_4: '',
        label_5: '',
        label_6: '',
        label_at_bottom: false,
      },
    body: p => {

        const gen_nets = (p) => {
          const all_nets = [
            p.net_1.str, p.net_2.str, p.net_3.str,
            p.net_4.str, p.net_5.str, p.net_6.str,
          ];
          const all_labels = [
            p.label_1, p.label_2, p.label_3,
            p.label_4, p.label_5, p.label_6,
          ];

          pad_cnt = p.pads;
          if(pad_cnt > all_nets.length || pad_cnt > all_labels.length) {
            pad_cnt = Math.min(all_nets.length, all_labels.length);
          }

          let nets = [];
          for(let i = 0; i < pad_cnt; i++) {
            let net = [
              all_nets[i],
              all_labels[i],
            ];
            nets.push(net);
          }

          return nets;
        }

        const gen_pad = (pad_idx, pad_cnt, net_str, net_label, width, height, space, rot, layer, label_at_bottom, pads_type) =>
        {
            // Calculate the pad position from center
            const pos_x_raw = (width + space) * pad_idx;

            // Adjust it so that the pads are centered in the middle
            const pos_x = (
              pos_x_raw - (width + space) * (pad_cnt - 1) / 2
            );

            let label_pos_y = -1 * (height / 2 + 0.2);
            let label_justify_direction = "left";
            if(label_at_bottom) {
              label_pos_y = label_pos_y * -1;
              label_justify_direction = "right";
            }

            if(label_at_bottom == false || layer == 'B') {
              if((rot > 0 && rot <= 180) || (rot <= -180)) {
                label_justify_direction = "right";
              } else {
                label_justify_direction = "left";
              }
            } else {
              if((rot > 0 && rot <= 180) || (rot <= -180)) {
                label_justify_direction = "left";
              } else {
                label_justify_direction = "right";
              }
            }

            let justify_mirror = '';
            if(layer == 'B') {
              justify_mirror = 'mirror'
            }

            let label_justify = '';
            if(justify_mirror != '' || label_justify_direction != '') {
              label_justify = `(justify ${label_justify_direction} ${justify_mirror})`;
            }

            pad_type_str ='smd'
            layers_postfix_str = ''
            drill_str =''
            layer_ch = layer
    
            if (pads_type=='through-hole') {
                pad_type_str = 'thru_hole'
                layer_ch = '*'
                drill_str = `(drill ${p.drill_size})`
                layers_postfix_str = '(remove_unused_layers) (keep_end_layers) (zone_layer_connections) '
            }

            let pad = `
                (pad ${pad_idx + 1} ${pad_type_str} rect (at ${pos_x} 0 ${rot}) (size ${width} ${height}) ${drill_str}(layers ${layer_ch}.Cu ${layer_ch}.Paste ${layer_ch}.Mask) ${layers_postfix_str}${net_str})
            `

            if(net_label) {
              pad += `
                (fp_text user "${net_label}" (at ${pos_x} ${label_pos_y} ${90 + rot}) (layer ${layer}.SilkS)
                  (effects (font (size 1 1) (thickness 0.1)) ${label_justify})
                )
              `
            }

            return pad;
        }

        const gen_pads = (nets, width, height, space, rot, layer, label_at_bottom, mirror, pads_type) => {

            if(mirror) {
                nets = nets.slice().reverse();
            }

            let pads = '';
            for (let [net_idx, net] of nets.entries()) {

                const net_str = net[0];
                const net_label = net[1];

                const pad = gen_pad(
                  net_idx,
                  nets.length,
                  net_str,
                  net_label,
                  width,
                  height,
                  space,
                  rot,
                  layer,
                  label_at_bottom,
                  pads_type,
                );

                pads += pad;
            }

            return pads;
        }

        const nets = gen_nets(p);

        let pads_front = '';
        if(p.side == 'F' || p.reverse) {
          pads_front = gen_pads(
            nets,
            p.width, p.height, p.space, p.rot, "F",
            p.label_at_bottom, false, p.pads_type,
          );
        }

        let pads_back = '';
        if(p.side == 'B' || p.reverse) {
          pads_back = gen_pads(
            nets,
            p.width, p.height, p.space, p.rot, "B",
            p.label_at_bottom, p.mirror_nets, p.pads_type
          );
        }
        const fp = `
          (module pads (layer F.Cu) (tedit 6446BF3D)
            ${p.at /* parametric position */}
            (attr smd)

            (fp_text reference "${p.ref}" (at 0 2.2) (layer F.SilkS) ${p.ref_hide}
              (effects (font (size 1 1) (thickness 0.15)))
            )
            ${pads_front}
            ${pads_back}
          )
        `

        return fp;
    }
}
