export function normalizedPlanarUvs(positionValues) {
  const positions = Array.from(positionValues || []);
  if (!positions.length) return [];
  if (positions.length % 3 !== 0) {
    throw new Error("positionValues must contain xyz triples");
  }
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;
  for (let index = 0; index < positions.length; index += 3) {
    minX = Math.min(minX, Number(positions[index]));
    maxX = Math.max(maxX, Number(positions[index]));
    minY = Math.min(minY, Number(positions[index + 1]));
    maxY = Math.max(maxY, Number(positions[index + 1]));
  }
  const spanX = Math.max(maxX - minX, 1e-9);
  const spanY = Math.max(maxY - minY, 1e-9);
  const uvs = [];
  for (let index = 0; index < positions.length; index += 3) {
    uvs.push(
      (Number(positions[index]) - minX) / spanX,
      (Number(positions[index + 1]) - minY) / spanY,
    );
  }
  return uvs;
}
